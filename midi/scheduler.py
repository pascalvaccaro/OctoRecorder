import time
from typing import Optional
from reactivex import from_iterable
from reactivex.abc import ObserverBase
from reactivex.scheduler import EventLoopScheduler
from reactivex.disposable import CompositeDisposable, MultipleAssignmentDisposable
from midi.messages import (
    MidiMessage,
    MidiNote,
    QMidiMessage,
    MidiCC,
    is_track_selection,
)


class MidiScheduler(EventLoopScheduler):
    _lock = False
    _midiout = QMidiMessage()
    _flowrate = 0.005

    def schedule_out(self, action, state: Optional[MidiMessage] = None):
        if state is None:
            return
        if isinstance(state, MidiNote) and not self._lock:
            self.schedule(action, state)
        else:
            self._midiout.add(state)

        if not self._lock:
            self._lock = True
            rate = self._flowrate
            while len(self._midiout) > 0:
                start = time.time()
                msg = self._midiout.pop()
                self.schedule_relative(rate, action, msg)
                rate += self._flowrate - time.time() + start
            self._lock = False

    def schedule_in(self, dev, final: ObserverBase):
        disp = MultipleAssignmentDisposable()
        disp.disposable = from_iterable(dev.init_actions).subscribe(
            final.on_next, final.on_error, scheduler=self
        )

        def action(sched, state):
            try:
                start = time.time()
                if dev.is_closed:
                    final.on_completed()
                    disp.dispose()
                    return disp
                cdisp = CompositeDisposable(disp.disposable)
                messages: QMidiMessage[MidiMessage] = QMidiMessage(dev.iter_pending)

                while len(messages) > 0:
                    item = messages.pop()
                    if item.type == "control_change" and is_track_selection(item, messages):
                        dev.channel = item.channel # type: ignore
                        break
                    elif item.bytes() != state:
                        cdisp.add(
                            dev.to_messages(item).subscribe(
                                final.on_next, final.on_error, scheduler=sched
                            )
                        )
                        dev.debug(item)
                        state = item.bytes()

                delta = self._flowrate - min(time.time() - start, self._flowrate)
                cdisp.add(sched.schedule_relative(delta, action, state))
                disp.disposable = cdisp
                return disp
            except Exception as e:
                final.on_error(e)

        return self.schedule(action, [])


midi_scheduler = MidiScheduler()
