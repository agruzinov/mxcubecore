from HardwareRepository.HardwareObjects.MD2Motor import MD2Motor
from HardwareRepository.HardwareObjects.abstract.AbstractMotor import MotorStates
import logging
import math


class MicrodiffSamplePseudo(MD2Motor):
    def __init__(self, name):
        MD2Motor.__init__(self, name)

        self.actuator_name = name
        self.sampx = None
        self.sampy = None
        self.phi = None
        self.direction = None

        self.motorState = MotorStates.NOTINITIALIZED

    def init(self):
        self.direction = self.getProperty("direction")
        self.sampx = self.getObjectByRole("sampx")
        self.sampy = self.getObjectByRole("sampy")
        self.phi = self.getObjectByRole("phi")
        self.connect(self.sampx, "positionChanged", self.real_motor_moved)
        self.connect(self.sampx, "stateChanged", self.real_motor_changed)
        self.connect(self.sampy, "positionChanged", self.real_motor_moved)
        self.connect(self.sampy, "stateChanged", self.real_motor_changed)
        self.connect(self.phi, "positionChanged", self.real_motor_moved)
        self.connect(self.phi, "stateChanged", self.real_motor_changed)

    def real_motor_moved(self, _):

        self.motorPositionChanged(self.get_value())

    def updateMotorState(self):
        states = [m.getState() for m in (self.sampx, self.sampy, self.phi)]
        error_states = [
            state
            in (MotorStates.UNUSABLE, MotorStates.NOTINITIALIZED, MotorStates.ONLIMIT)
            for state in states
        ]
        moving_state = [
            state in (MotorStates.MOVING, MotorStates.MOVESTARTED) for state in states
        ]

        if any(error_states):
            self.motorState = MotorStates.UNUSABLE
        elif any(moving_state):
            self.motorState = MotorStates.MOVING
        else:
            self.motorState = MotorStates.READY

        self.motorStateChanged(self.motorState)

    def motorStateChanged(self, state):
        logging.getLogger().debug(
            "%s: in motorStateChanged: motor state changed to %s", self.name(), state
        )
        self.emit("stateChanged", (self.motorState,))

    def get_value(self):
        sampx = self.sampx.get_value()
        sampy = self.sampy.get_value()
        phi = self.phi.get_value()
        if phi:
            phi = math.radians(self.phi.get_value())
            if self.direction == "horizontal":
                new_pos = sampx * math.cos(phi) + sampy * math.sin(phi)
            else:
                new_pos = sampx * math.sin(-phi) + sampy * math.cos(-phi)
            return new_pos

    def getState(self):
        if self.motorState == MotorStates.NOTINITIALIZED:
            self.updateMotorState()
        return self.motorState

    def real_motor_changed(self, _):
        self.updateMotorState()

    def motorPositionChanged(self, absolutePosition):
        self.emit("positionChanged", (absolutePosition,))

    def move(self, absolutePosition):
        sampx = self.sampx.get_value()
        sampy = self.sampy.get_value()
        phi = math.radians(self.phi.get_value())
        if self.direction == "horizontal":
            ver = sampx * math.sin(-phi) + sampy * math.cos(-phi)
            self.sampx.set_value(
                absolutePosition * math.cos(-phi) + ver * math.sin(-phi)
            )
            self.sampy.set_value(
                -absolutePosition * math.sin(-phi) + ver * math.cos(-phi)
            )
        else:
            hor = sampx * math.cos(phi) + sampy * math.sin(phi)
            self.sampx.set_value(
                absolutePosition * math.sin(-phi) + hor * math.cos(-phi)
            )
            self.sampy.set_value(
                absolutePosition * math.cos(-phi) - hor * math.sin(-phi)
            )

    def _motor_abort(self):
        for m in (self.phi, self.sampx, self.sampy):
            m.stop()
