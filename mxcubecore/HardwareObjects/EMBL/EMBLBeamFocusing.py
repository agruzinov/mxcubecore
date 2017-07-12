#
#  Project: MXCuBE
#  https://github.com/mxcube.
#
#  This file is part of MXCuBE software.
#
#  MXCuBE is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  MXCuBE is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with MXCuBE.  If not, see <http://www.gnu.org/licenses/>.

import gevent
import logging
from _tine import query as tinequery
from HardwareRepository.BaseHardwareObjects import HardwareObject


__credits__ = ["EMBL Hamburg"]
__version__ = "2.3."
__category__ = "General"


class EMBLBeamFocusing(HardwareObject):
    """Hardware Object is used to evaluate and set beam focusing mode.
    """

    def __init__(self, name):
        HardwareObject.__init__(self, name)

        self.active_focus_mode = None
        self.size = [9999, 9999]
        self.focus_modes = None
        self.focus_motors_dict = None
        self.motors_groups = []

        self.cmd_set_calibration_name = None
        self.cmd_set_phase = None

    def init(self):
        """Reads available focusing modes from the config xml and
           attaches corresponding motors
        """
        self.focus_modes = []
        for focus_mode in self['focusModes']:
            self.focus_modes.append(\
                 {'modeName': focus_mode.modeName,
                  'lensCombination': eval(focus_mode.lensCombination),
                  'lensModes': eval(focus_mode.lensModes),
                  'size': eval(focus_mode.size),
                  'message': eval(focus_mode.message),
                  'diverg': eval(focus_mode.divergence)})
        self.focus_motors_dict = {}

        focus_motors = []
        focus_motors = eval(self.getProperty('focusMotors'))

        for focus_motor in focus_motors:
            self.focus_motors_dict[focus_motor] = []

        #TODO
        self.motors_groups = [self.getObjectByRole("P14ExpTbl"),
                              self.getObjectByRole("P14KB"),
                              self.getObjectByRole("P14DetTrans"),
                              self.getObjectByRole("P14BCU"),
                              self.getObjectByRole("slitsMotors")]
        

        if len(self.motors_groups) > 0:
            for motors_group in self.motors_groups:
                self.connect(motors_group,
                             'mGroupFocModeChanged',
                             self.motor_group_focus_mode_changed)
        else:
            logging.getLogger("HWR").debug('BeamFocusing: No motors defined')
            self.active_focus_mode = self.focus_modes[0]['modeName']
            self.size = self.focus_modes[0]['size']
            self.update_values()

        self.cmd_set_calibration_name = self.getCommandObject(\
            'cmdSetCallibrationName')
        try:
            self.cmd_set_phase = eval(self.getProperty('setPhaseCmd'))
        except:
            pass

    def get_focus_motors(self):
        """Returns a list with all focusing motors"""
        focus_motors = []
        if self.motors_groups is not None:
            for motors_group in self.motors_groups:
                motors_group_list = motors_group.get_motors_dict()
                for motor in motors_group_list:
                    focus_motors.append(motor)
        return focus_motors

    def motor_group_focus_mode_changed(self, value):
        """Called if motors group focusing is changed

        :param value: focusing mode
        :type value: str or None
        """
        motors_group_foc_mode = eval(value)
        for motor in motors_group_foc_mode:
            if motor in self.focus_motors_dict:
                self.focus_motors_dict[motor] = motors_group_foc_mode[motor]

        prev_mode = self.active_focus_mode
        self.active_focus_mode, self.size = self.get_active_focus_mode()

        if prev_mode != self.active_focus_mode:
            logging.getLogger("HWR").info('Focusing: %s mode detected' %\
                                          self.active_focus_mode)
            self.emit('focusingModeChanged', self.active_focus_mode, self.size)
            if self.cmd_set_calibration_name and self.active_focus_mode:
                self.cmd_set_calibration_name(self.active_focus_mode.lower())

    def get_focus_mode_names(self):
        """Returns defined focus modes names"""
        names = []
        for focus_mode in self.focus_modes:
            names.append(focus_mode['modeName'])
        return names

    def get_focus_mode_message(self, focus_mode_name):
        """Returns messages used when a new focusing mode is requisted.

        :param focus_mode_name: name of the mode
        :type focus_mode_name: str
        """
        for focus_mode in self.focus_modes:
            if focus_mode['modeName'] == focus_mode_name:
                return focus_mode['message']

    def get_available_lens_modes(self, focus_mode_name=None):
        """Get available CRL lens combination for the given focusing mode

        :param focus_mode_name: requested focusing mode. If None passed then
                                current focusing mode is used
        :type focus_mode_name: str
        """
        lens_modes = []

        if focus_mode_name == None:
            focus_mode_name = self.active_focus_mode
        for focus_mode in self.focus_modes:
            if focus_mode['modeName'] == focus_mode_name:
                lens_modes = focus_mode['lensModes']
        return lens_modes

    def get_lens_combination(self, focus_mode_name=None):
        """Returns available lens combination for the given focusing mode

        :param focus_mode_name: requested focusing mode. If None passed then
                                current focusing mode is used
        :type focus_mode_name: str
        """
        if focus_mode_name == None:
            focus_mode_name, beam_size = self.get_active_focus_mode()

        for focus_mode in self.focus_modes:
            if focus_mode['modeName'] == focus_mode_name:
                return focus_mode['lensCombination']

    def get_active_focus_mode(self):
        """Evaluates and returns active focusing mode"""
        if len(self.focus_motors_dict) > 0:
            active_focus_mode = None
            for focus_mode in self.focus_modes:
                self.size = focus_mode['size']
                active_focus_mode = focus_mode['modeName']
                for motor in self.focus_motors_dict:
                    if len(self.focus_motors_dict[motor]) == 0:
                        active_focus_mode = None
                        self.size = [9999, 9999]
                    elif active_focus_mode not in \
                        self.focus_motors_dict[motor]:
                        active_focus_mode = None
                        self.size = [9999, 9999]
                        break
                if active_focus_mode is not None:
                    break
            if active_focus_mode != self.active_focus_mode:
                self.active_focus_mode = active_focus_mode
        return self.active_focus_mode, self.size

    def get_focus_mode(self):
        """Returns active focusing mode"""
        if self.active_focus_mode:
            return self.active_focus_mode.lower()

    def set_motor_focus_mode(self, motor_name, focus_mode):
        """Sets focusing mode of a selected motor

        :param motor_name: motor name
        :type motor_name: str
        :param focus_mode: requested focusing mode
        :type focus_mode: str
        """
        if focus_mode is not None:
            for motor in self.motors_groups:
                motor.set_motor_focus_mode(motor_name, focus_mode)

    def set_focus_mode(self, focus_mode):
        """Sets focusing mode to all motors

        :param focus_mode: requested focusing mode
        :type focus_mode: str
        """
        gevent.spawn(self.focus_mode_task,
                     focus_mode)
        self.emit('focusingModeRequested', focus_mode)

    def focus_mode_task(self, focus_mode):
        """Gevent task to set focusing mode

        :param focus_mode: requested focusing mode
        :type focus_mode: str
        """
        if focus_mode and self.cmd_set_phase:
            tinequery(self.cmd_set_phase['address'],
                      self.cmd_set_phase['property'],
                      self.cmd_set_phase['argument'])
            if self.motors_groups:
                for motors_group in self.motors_groups:
                    motors_group.set_motor_group_focus_mode(focus_mode)
        else:
            #No motors defined
            self.active_focus_mode = focus_mode

    def get_divergence_hor(self):
        """Returns horizontal beam divergence"""
        for focus_mode in self.focus_modes:
            if focus_mode['modeName'] == self.active_focus_mode:
                return focus_mode['diverg'][0]

    def get_divergence_ver(self):
        """Returns vertical beam divergence"""
        for focus_mode in self.focus_modes:
            if focus_mode['modeName'] == self.active_focus_mode:
                return focus_mode['diverg'][1]

    def update_values(self):
        """Reemits available signals"""
        self.emit('focusingModeChanged',
                  self.active_focus_mode,
                  self.size)
