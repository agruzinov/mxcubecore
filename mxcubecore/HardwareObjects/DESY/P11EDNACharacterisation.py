import os
import logging
import binascii

from mxcubecore.model import queue_model_objects as qmo
from mxcubecore.model import queue_model_enumerables as qme

from mxcubecore.HardwareObjects.SecureXMLRpcRequestHandler import (
    SecureXMLRpcRequestHandler,
)
from mxcubecore import HardwareRepository as HWR
from mxcubecore.HardwareObjects.abstract.AbstractCharacterisation import (
    AbstractCharacterisation,
)

from mxcubecore.HardwareObjects.EDNACharacterisation import EDNACharacterisation

from XSDataMXCuBEv1_4 import XSDataInputMXCuBE
from XSDataMXCuBEv1_4 import XSDataMXCuBEDataSet
from XSDataMXCuBEv1_4 import XSDataResultMXCuBE

from XSDataCommon import XSDataAngle
from XSDataCommon import XSDataBoolean
from XSDataCommon import XSDataDouble
from XSDataCommon import XSDataFile
from XSDataCommon import XSDataImage
from XSDataCommon import XSDataFlux
from XSDataCommon import XSDataLength
from XSDataCommon import XSDataTime
from XSDataCommon import XSDataWavelength
from XSDataCommon import XSDataInteger
from XSDataCommon import XSDataSize
from XSDataCommon import XSDataString

import triggerUtils

# from edna_test_data import EDNA_DEFAULT_INPUT
# from edna_test_data import EDNA_TEST_DATA


class P11EDNACharacterisation(EDNACharacterisation):
    def __init__(self, name):
        super().__init__(name)

        self.collect_obj = None
        self.result = None
        self.edna_default_file = None
        self.start_edna_command = None

    def _run_edna(self, input_file, results_file, process_directory):
        """Starts EDNA"""
        msg = "Starting EDNA characterisation using xml file %s" % input_file
        logging.getLogger("queue_exec").info(msg)

        args = (self.start_edna_command, input_file, results_file, process_directory)
        # subprocess.call("%s %s %s %s" % args, shell=True)

        # Test run DESY
        self.edna_maxwell(process_directory, input_file, results_file)

        self.result = None
        if os.path.exists(results_file):
            self.result = XSDataResultMXCuBE.parseFile(results_file)

        return self.result

    def edna_maxwell(self, process_directory, inputxml, outputxml):
        """
        The function `edna_maxwell` is used to execute a command on a remote cluster using SSH and SBATCH.
        
        :param process_directory: The `process_directory` parameter is the directory where the processing
        will take place. It is a string that represents the path to the directory
        :param inputxml: The inputxml parameter is the path to the input XML file that will be used as
        input for the EDNA process
        :param outputxml: The `outputxml` parameter is the path to the output XML file that will be
        generated by the EDNA process
        """
        # TODO: Check if this function is still needed or adapt to use edna_command from XML config.

        self.log.debug(
            '=======EDNA========== PROCESS DIRECTORY="%s"' % process_directory
        )
        self.log.debug('=======EDNA========== IN="%s"' % inputxml)
        self.log.debug('=======EDNA========== OUT="%s"' % outputxml)

        btHelper = triggerUtils.Trigger()
        ssh = btHelper.get_ssh_command()
        sbatch = btHelper.get_sbatch_command(
            jobname_prefix="edna",
            job_dependency="singleton",
            logfile_path=process_directory.replace("/gpfs", "/beamline/p11")
            + "/edna.log",
        )

        cmd = (
            "/asap3/petra3/gpfs/common/p11/processing/edna_sbatch.sh "
            + "{inxml:s} {outxml:s} {processpath:s}"
        ).format(
            inxml=inputxml.replace("/gpfs", "/beamline/p11"),
            outxml=outputxml.replace("/gpfs", "/beamline/p11"),
            processpath=process_directory.replace("/gpfs", "/beamline/p11") + "/edna",
        )

        self.mkdir_with_mode(process_directory + "/edna", mode=0o777)

        # Check path conversion
        inxml = inputxml.replace("/gpfs", "/beamline/p11")
        outxml = outputxml.replace("/gpfs", "/beamline/p11")
        processpath = process_directory.replace("/gpfs", "/beamline/p11") + "/edna"
        self.log.debug(
            '=======EDNA========== CLUSTER PROCESS DIRECTORY="%s"' % processpath
        )
        self.log.debug('=======EDNA========== CLUSTER IN="%s"' % inxml)
        self.log.debug('=======EDNA========== CLUSTER OUT="%s"' % outxml)

        self.log.debug('=======EDNA========== ssh="%s"' % ssh)
        self.log.debug('=======EDNA========== sbatch="%s"' % sbatch)
        self.log.debug('=======EDNA========== executing process cmd="%s"' % cmd)
        self.log.debug(
            '=======EDNA========== {ssh:s} "{sbatch:s} --wrap \\"{cmd:s}\\""'.format(
                ssh=ssh, sbatch=sbatch, cmd=cmd
            )
        )

        print(
            '{ssh:s} "{sbatch:s} --wrap \\"{cmd:s}"\\"'.format(
                ssh=ssh, sbatch=sbatch, cmd=cmd
            )
        )

        os.system(
            '{ssh:s} "{sbatch:s} --wrap \\"{cmd:s}"\\"'.format(
                ssh=ssh, sbatch=sbatch, cmd=cmd
            )
        )

    def input_from_params(self, data_collection, char_params):
        edna_input = XSDataInputMXCuBE.parseString(self.edna_default_input)

        if data_collection.id:
            edna_input.setDataCollectionId(XSDataInteger(data_collection.id))

        # Beam object
        beam = edna_input.getExperimentalCondition().getBeam()

        try:
            transmission = HWR.beamline.transmission.get_value()
            beam.setTransmission(XSDataDouble(transmission))
        except AttributeError:
            import traceback

            logging.getLogger("HWR").debug(
                "EDNACharacterisation. transmission not saved "
            )
            logging.getLogger("HWR").debug(traceback.format_exc())

        try:
            wavelength = HWR.beamline.energy.get_wavelength()
            beam.setWavelength(XSDataWavelength(wavelength))
        except AttributeError:
            pass

        try:
            beam.setFlux(XSDataFlux(HWR.beamline.flux.get_value()))
        except AttributeError:
            pass

        try:
            min_exp_time = self.collect_obj.detector_hwobj.get_exposure_time_limits()[0]
            beam.setMinExposureTimePerImage(XSDataTime(min_exp_time))
        except AttributeError:
            pass

        try:
            beamsize = self.collect_obj.beam_info_hwobj.get_beam_size()

            if None not in beamsize:
                beam.setSize(
                    XSDataSize(
                        x=XSDataLength(float(beamsize[0])),
                        y=XSDataLength(float(beamsize[1])),
                    )
                )
        except AttributeError:
            pass

        # Optimization parameters
        diff_plan = edna_input.getDiffractionPlan()

        aimed_i_sigma = XSDataDouble(char_params.aimed_i_sigma)
        aimed_completness = XSDataDouble(char_params.aimed_completness)
        aimed_multiplicity = XSDataDouble(char_params.aimed_multiplicity)
        aimed_resolution = XSDataDouble(char_params.aimed_resolution)

        complexity = char_params.strategy_complexity
        complexity = XSDataString(qme.STRATEGY_COMPLEXITY[complexity])

        permitted_phi_start = XSDataAngle(char_params.permitted_phi_start)
        _range = char_params.permitted_phi_end - char_params.permitted_phi_start
        rotation_range = XSDataAngle(_range)

        if char_params.aimed_i_sigma:
            diff_plan.setAimedIOverSigmaAtHighestResolution(aimed_i_sigma)

        if char_params.aimed_completness:
            diff_plan.setAimedCompleteness(aimed_completness)

        if char_params.use_aimed_multiplicity:
            diff_plan.setAimedMultiplicity(aimed_multiplicity)

        if char_params.use_aimed_resolution:
            diff_plan.setAimedResolution(aimed_resolution)

        diff_plan.setComplexity(complexity)
        diff_plan.setStrategyType(XSDataString(char_params.strategy_program))

        if char_params.use_permitted_rotation:
            diff_plan.setUserDefinedRotationStart(permitted_phi_start)
            diff_plan.setUserDefinedRotationRange(rotation_range)

        # Vertical crystal dimension
        sample = edna_input.getSample()
        sample.getSize().setY(XSDataLength(char_params.max_crystal_vdim))
        sample.getSize().setZ(XSDataLength(char_params.min_crystal_vdim))

        # Radiation damage model
        sample.setSusceptibility(XSDataDouble(char_params.rad_suscept))
        sample.setChemicalComposition(None)
        sample.setRadiationDamageModelBeta(XSDataDouble(char_params.beta / 1e6))
        sample.setRadiationDamageModelGamma(XSDataDouble(char_params.gamma / 1e6))

        diff_plan.setForcedSpaceGroup(XSDataString(char_params.space_group))

        # Characterisation type - Routine DC
        if char_params.use_min_dose:
            pass

        if char_params.use_min_time:
            time = XSDataTime(char_params.min_time)
            diff_plan.setMaxExposureTimePerDataCollection(time)

        # Account for radiation damage
        if char_params.induce_burn:
            self._modify_strategy_option(diff_plan, "-DamPar")

        # Characterisation type - SAD
        if char_params.opt_sad:
            if char_params.auto_res:
                diff_plan.setAnomalousData(XSDataBoolean(True))
            else:
                diff_plan.setAnomalousData(XSDataBoolean(False))
                self._modify_strategy_option(diff_plan, "-SAD yes")
                diff_plan.setAimedResolution(XSDataDouble(char_params.sad_res))
        else:
            diff_plan.setAnomalousData(XSDataBoolean(False))

        # Data set
        data_set = XSDataMXCuBEDataSet()
        acquisition_parameters = data_collection.acquisitions[0].acquisition_parameters
        path_template = data_collection.acquisitions[0].path_template

        # Make sure there is a proper path conversion between different mount points
        print(
            "======= Characterisation path template ====", path_template.directory
        )  # /gpfs/current/raw

        image_dir = path_template.directory.replace(
            "/gpfs/current", triggerUtils.get_beamtime_metadata()[2]
        )

        print(image_dir)

        path_str = os.path.join(image_dir, path_template.get_image_file_name())
        print(path_template.xds_dir)

        characterisation_dir = path_template.xds_dir.replace(
            "/autoprocessing_", "/characterisation_"
        )

        os.makedirs(characterisation_dir, mode=0o755, exist_ok=True)

        for img_num in range(int(acquisition_parameters.num_images)):
            image_file = XSDataImage()
            path = XSDataString()
            path.value = path_str % (img_num + 1)
            image_file.path = path
            image_file.number = XSDataInteger(img_num + 1)
            data_set.addImageFile(image_file)

        edna_input.addDataSet(data_set)
        edna_input.process_directory = characterisation_dir
        return edna_input

    def mkdir_with_mode(self, directory, mode):
        """
        The function creates a directory with a specified mode if it does not already exist.
        
        :param directory: The "directory" parameter is the path of the directory that you want to
        create. It can be an absolute path or a relative path
        :param mode: The "mode" parameter in the above code refers to the permissions that will be set
        for the newly created directory. It is an optional parameter that specifies the access mode for
        the directory. The access mode is a numeric value that represents the permissions for the
        directory
        """
        if not os.path.isdir(directory):
            oldmask = os.umask(000)
            os.makedirs(directory, mode=mode)
            os.umask(oldmask)
            # self.checkPath(directory,force=True)

            self.log.debug("local directory created")
