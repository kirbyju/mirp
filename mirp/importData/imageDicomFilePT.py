import numpy as np
import datetime

from typing import Union, Tuple, List, Optional, Dict, Any

from mirp.imageSUV import SUVscalingObj
from mirp.importData.imageDicomFile import ImageDicomFile
from mirp.imageMetaData import get_pydicom_meta_tag, convert_dicom_time, parse_image_correction


class ImageDicomFilePT(ImageDicomFile):
    def __init__(
            self,
            file_path: Union[None, str] = None,
            dir_path: Union[None, str] = None,
            sample_name: Union[None, str, List[str]] = None,
            file_name: Union[None, str] = None,
            image_name: Union[None, str] = None,
            image_modality: Union[None, str] = None,
            image_file_type: Union[None, str] = None,
            image_data: Union[None, np.ndarray] = None,
            image_origin: Union[None, Tuple[float]] = None,
            image_orientation: Union[None, np.ndarray] = None,
            image_spacing: Union[None, Tuple[float]] = None,
            image_dimensions: Union[None, Tuple[int]] = None,
            **kwargs):

        super().__init__(
            file_path=file_path,
            dir_path=dir_path,
            sample_name=sample_name,
            file_name=file_name,
            image_name=image_name,
            image_modality=image_modality,
            image_file_type=image_file_type,
            image_data=image_data,
            image_origin=image_origin,
            image_orientation=image_orientation,
            image_spacing=image_spacing,
            image_dimensions=image_dimensions
        )

    def is_stackable(self, stack_images: str):
        return True

    def create(self):
        return self

    def load_data(self, **kwargs):
        image_data = self.load_data_generic()

        # TODO: integrate SUV computations locally.
        suv_conversion_object = SUVscalingObj(dcm=self.image_metadata)
        scale_factor = suv_conversion_object.get_scale_factor(suv_normalisation="bw")

        # Convert to SUV
        image_data *= scale_factor

        # Update relevant tags in the metadata
        self.image_metadata = suv_conversion_object.update_dicom_header(dcm=self.image_metadata)

    def export_metadata(self, self_only=False, **kwargs) -> Optional[Dict[str, Any]]:
        if not self_only:
            metadata = super().export_metadata()
        else:
            metadata = {}

        self.load_metadata()

        dcm_meta_data = []

        # Scanner type
        scanner_type = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0008, 0x1090),
            tag_type="str"
        )
        if scanner_type is not None:
            dcm_meta_data += [("scanner_type", scanner_type)]

        # Scanner manufacturer
        manufacturer = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0008, 0x0070),
            tag_type="str"
        )
        if manufacturer is not None:
            dcm_meta_data += [("manufacturer", manufacturer)]

        # Image type
        image_type = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0008, 0x0008),
            tag_type="str"
        )
        if image_type is not None:
            dcm_meta_data += [("image_type", image_type)]

        # Time of flight information (0018,9755)
        time_of_flight = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0018, 0x9755),
            tag_type="str"
        )
        if time_of_flight is not None:
            dcm_meta_data += [("time_of_flight", time_of_flight)]

        # Radiopharmaceutical
        if get_pydicom_meta_tag(dcm_seq=self.image_metadata, tag=(0x0054, 0x0016), tag_type=None, test_tag=True):
            radiopharmaceutical = get_pydicom_meta_tag(
                dcm_seq=self.image_metadata[0x0054, 0x0016][0], tag=(0x0018, 0x0031), tag_type="str")
        else:
            radiopharmaceutical = None
        if radiopharmaceutical is not None:
            dcm_meta_data += [("radiopharmaceutical", radiopharmaceutical)]

        # Uptake time - acquisition start
        acquisition_ref_time = convert_dicom_time(
            date_str=get_pydicom_meta_tag(dcm_seq=self.image_metadata, tag=(0x0008, 0x0022), tag_type="str"),
            time_str=get_pydicom_meta_tag(dcm_seq=self.image_metadata, tag=(0x0008, 0x0032), tag_type="str")
        )

        # Uptake time - administration (0018,1078) is the administration start DateTime
        if get_pydicom_meta_tag(dcm_seq=self.image_metadata, tag=(0x0054, 0x0016), test_tag=True):
            radio_admin_ref_time = convert_dicom_time(
                datetime_str=get_pydicom_meta_tag(
                    dcm_seq=self.image_metadata[0x0054, 0x0016][0], tag=(0x0018, 0x1078), tag_type="str")
            )

            if radio_admin_ref_time is None:
                # If unsuccessful, attempt determining administration time from (0x0018, 0x1072), which is the
                # administration start time.
                radio_admin_ref_time = convert_dicom_time(
                    date_str=get_pydicom_meta_tag(dcm_seq=self.image_metadata, tag=(0x0008, 0x0022), tag_type="str"),
                    time_str=get_pydicom_meta_tag(
                        dcm_seq=self.image_metadata[0x0054, 0x0016][0], tag=(0x0018, 0x1072), tag_type="str"
                    )
                )
        else:
            radio_admin_ref_time = None

        if radio_admin_ref_time is None:
            # If neither (0x0018, 0x1078) or (0x0018, 0x1072) are present, attempt to read private tags.
            # GE tags - note that due to anonymisation, acquisition time may be different then reported.
            acquisition_ref_time = convert_dicom_time(get_pydicom_meta_tag(
                dcm_seq=self.image_metadata, tag=(0x0009, 0x100d), tag_type="str"))
            radio_admin_ref_time = convert_dicom_time(get_pydicom_meta_tag(
                dcm_seq=self.image_metadata, tag=(0x0009, 0x103b), tag_type="str"))

        if radio_admin_ref_time is not None and acquisition_ref_time is not None:

            day_diff = abs(radio_admin_ref_time - acquisition_ref_time).days
            if day_diff > 1:
                # Correct for de-identification mistakes (i.e. administration time was de-identified correctly,
                # but acquisition time not). We do not expect that the difference between the two is more than a
                # day, or even more than a few hours at most.
                if radio_admin_ref_time > acquisition_ref_time:
                    radio_admin_ref_time -= datetime.timedelta(days=day_diff)
                else:
                    radio_admin_ref_time += datetime.timedelta(days=day_diff)

            if radio_admin_ref_time > acquisition_ref_time:
                # Correct for overnight
                radio_admin_ref_time -= datetime.timedelta(days=1)

            # Calculate uptake time in minutes
            uptake_time = ((acquisition_ref_time - radio_admin_ref_time).seconds / 60.0)
        else:
            uptake_time = None

        if uptake_time is not None:
            dcm_meta_data += [("uptake_time", uptake_time)]

        # Reconstruction method
        reconstruction_method = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0054, 0x1103),
            tag_type="str"
        )
        if reconstruction_method is not None:
            dcm_meta_data += [("reconstruction_method", reconstruction_method)]

        # Convolution kernel
        kernel = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0018, 0x1210),
            tag_type="str"
        )
        if kernel is not None:
            dcm_meta_data += [("kernel", kernel)]

        # Read reconstruction sequence (0018,9749)
        if get_pydicom_meta_tag(dcm_seq=self.image_metadata, tag=(0x0018, 0x9749), tag_type=None, test_tag=True):
            # Reconstruction type (0018,9749)(0018,9756)
            recon_type = get_pydicom_meta_tag(
                dcm_seq=self.image_metadata[0x0018, 0x9749][0],
                tag=(0x0018, 0x9756),
                tag_type="str"
            )
            if recon_type is not None:
                dcm_meta_data += [("reconstruction_type", recon_type)]

            # Reconstruction algorithm (0018,9749)(0018,9315)
            recon_algorithm = get_pydicom_meta_tag(
                dcm_seq=self.image_metadata[0x0018, 0x9749][0],
                tag=(0x0018, 0x9315),
                tag_type="str"
            )
            if reconstruction_method is not None:
                dcm_meta_data += [("reconstruction_algorithm", recon_algorithm)]

            # Is an iterative method? (0018,9749)(0018,9769)
            is_iterative = get_pydicom_meta_tag(
                dcm_seq=self.image_metadata[0x0018, 0x9749][0],
                tag=(0x0018, 0x9769),
                tag_type="str"
            )
            if is_iterative is not None:
                dcm_meta_data += [("iterative_method", is_iterative)]

            # Number of iterations (0018,9749)(0018,9739)
            n_iterations = get_pydicom_meta_tag(
                dcm_seq=self.image_metadata[0x0018, 0x9749][0],
                tag=(0x0018, 0x9739),
                tag_type="int"
            )
            if n_iterations is not None:
                dcm_meta_data += [("n_iterations", n_iterations)]

            # Number of subsets (0018,9749)(0018,9740)
            n_subsets = get_pydicom_meta_tag(
                dcm_seq=self.image_metadata[0x0018, 0x9749][0],
                tag=(0x0018, 0x9740),
                tag_type="int"
            )
            if n_subsets is not None:
                dcm_meta_data += [("n_subsets", n_subsets)]

        # Frame duration (converted from milliseconds to seconds)
        frame_duration = get_pydicom_meta_tag(
            dcm_seq=self.image_metadata,
            tag=(0x0018, 0x1242),
            tag_type="float"
        )
        if frame_duration is not None:
            dcm_meta_data += [("frame_duration", frame_duration / 1000.0)]

        # Image corrections
        image_corrections = get_pydicom_meta_tag(dcm_seq=dcm, tag=(0x0028, 0x0051), tag_type="str", default="")

        # Randoms correction method
        random_correction_method = get_pydicom_meta_tag(dcm_seq=dcm, tag=(0x0054, 0x1100), tag_type="str",
                                                        default="")

        # Attenuation correction method
        attenuation_correction_method = get_pydicom_meta_tag(dcm_seq=dcm, tag=(0x0054, 0x1101), tag_type="str",
                                                             default="")

        # Scatter correction method
        scatter_correction_method = get_pydicom_meta_tag(dcm_seq=dcm, tag=(0x0054, 0x1105), tag_type="str",
                                                         default="")

        # Load image corrections for comparison in case correction tags are missing.
        image_corrections = get_pydicom_meta_tag(dcm_seq=dcm, tag=(0x0028, 0x0051), tag_type="str", default="")
        image_corrections = image_corrections.replace(" ", "").replace("[", "").replace("]", "").replace("\'", "").split(sep=",")

        # Decay corrected DECY (0018,9758)
        decay_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9758), correction_abbr="DECY", image_corrections=image_corrections)

        # Attenuation corrected ATTN (0018,9759)
        attenuation_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9759), correction_abbr="ATTN", image_corrections=image_corrections)

        # Scatter corrected SCAT (0018,9760)
        scatter_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9760), correction_abbr="SCAT", image_corrections=image_corrections)

        # Dead time corrected DTIM (0018,9761)
        dead_time_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9761), correction_abbr="DTIM", image_corrections=image_corrections)

        # Gantry motion corrected MOTN (0018,9762)
        gantry_motion_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9762), correction_abbr="MOTN", image_corrections=image_corrections)

        # Patient motion corrected PMOT (0018,9763)
        patient_motion_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9763), correction_abbr="PMOT", image_corrections=image_corrections)

        # Count loss normalisation corrected CLN (0018,9764)
        count_loss_norm_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9764), correction_abbr="CLN", image_corrections=image_corrections)

        # Randoms corrected RAN (0018,9765)
        randoms_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9765), correction_abbr="RAN", image_corrections=image_corrections)

        # Non-uniform radial sampling corrected RADL (0018,9766)
        radl_corrected = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9766), correction_abbr="RADL", image_corrections=image_corrections)

        # Sensitivity calibrated DCAL (0018,9767)
        sensitivity_calibrated = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9767), correction_abbr="DCAL", image_corrections=image_corrections)

        # Detector normalisation correction NORM (0018,9768)
        detector_normalisation = parse_image_correction(dcm_seq=dcm, tag=(0x0018, 0x9768), correction_abbr="NORM", image_corrections=image_corrections)





        return metadata.update(dict(dcm_meta_data))
