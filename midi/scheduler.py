import time
from typing import Optional
from reactivex import from_iterable
from reactivex.abc import ObserverBase
from reactivex.scheduler import EventLoopScheduler
from reactivex.disposable import CompositeDisposable, MultipleAssignmentDisposable
from midi.messages import MidiMessage, TrackSelection


class MidiScheduler(EventLoopScheduler):
    _lock = False
    _midiout = []
    _flowrate = 0.005

    def schedule_out(self, action, state: Optional[MidiMessage] = None):
        if state is None or self._lock:
            return
        self._lock = True
        rate = self._flowrate
        with state.to_mido() as msg:
            start = time.time()
            self.schedule_relative(rate, action, msg)
            rate += self._flowrate - time.time() + start
        self._lock = False

    def schedule_in(self, dev, proxy: ObserverBase):
        disp = MultipleAssignmentDisposable()
        disp.disposable = from_iterable(dev.init_actions).subscribe(
            proxy.on_next, proxy.on_error
        )

        def action(sched, state):
            start = time.time()
            if dev.is_closed:
                proxy.on_completed()
                disp.dispose()
                return disp
            cdisp = CompositeDisposable(disp.disposable)
            try:
                with MidiMessage.from_mido(dev.messages) as msg:
                    if msg.bytes() != state:
                        cdisp.add(
                            dev.to_messages(msg).subscribe(
                                proxy.on_next, proxy.on_error, scheduler=sched
                            )
                        )
                        dev.debug(msg)
                        state = msg.bytes()
            except TrackSelection as e:
                dev.channel = e.channel
            except Exception as e:
                proxy.on_error(e)
            delta = self._flowrate - min(time.time() - start, self._flowrate)
            cdisp.add(sched.schedule_relative(delta, action, state))
            disp.disposable = cdisp
            return disp

        return self.schedule(action, [])


midi_scheduler = MidiScheduler()
