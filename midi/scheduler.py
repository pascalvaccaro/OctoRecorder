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
    ControlException,
    clean_messages,
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
            self._midiout.append(state)

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
            if dev.is_closed:
                final.on_completed()
                disp.dispose()
                return disp

            try:
                start = time.time()
                cdisp = CompositeDisposable(disp.disposable)
                midi_in = [
                    m
                    for m in dev.inport.iter_pending()
                    if m.type not in ["clock", "start"]
                ]
                (dev.server.send(msg) for msg in midi_in)
                client_in = []
                for port in dev.server:
                    client_in += [m for m in port.iter_pending()]
                all_messages: "list[MidiMessage]" = [*midi_in, *client_in]
                messages = QMidiMessage(
                    [m for m in all_messages if dev.select_message(m)]
                )

                while len(messages) > 0:
                    item = messages.pop()
                    try:
                        if item.bytes() != state:
                            cdisp.add(
                                dev.to_messages(item).subscribe(
                                    final.on_next, final.on_error, scheduler=sched
                                )
                            )
                            state = item.bytes()
                        messages = clean_messages(item, messages)
                    except ControlException as e:
                        dev.channel = e.channel
                        messages.clear()
                    finally:
                        dev.debug(item)

                delta = self._flowrate - min(time.time() - start, self._flowrate)
                cdisp.add(sched.schedule_relative(delta, action, state))
                disp.disposable = cdisp
                return disp
            except Exception as e:
                final.on_error(e)

        return self.schedule(action, [])


midi_scheduler = MidiScheduler()
