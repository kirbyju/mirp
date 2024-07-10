from functools import cache
from typing import Generator

import numpy as np

from mirp._features.rlm_matrix import MatrixRLM
from mirp._images.generic_image import GenericImage
from mirp._masks.base_mask import BaseMask
from mirp._features.histogram import HistogramDerivedFeature, get_discretisation_parameters
from mirp.settings.feature_parameters import FeatureExtractionSettingsClass


class FeatureRLM(HistogramDerivedFeature):

    def __init__(
            self,
            spatial_method: str,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.spatial_method = spatial_method.lower()

        # Perform close crop for RLM.
        self.cropping_distance = 0.0

    def get_matrix(
            self,
            image: GenericImage,
            mask: BaseMask,
    ) -> list[MatrixRLM]:
        # First discretise the image.
        image, mask = self.discretise_image(
            image=image,
            mask=mask,
            discretisation_method=self.discretisation_method,
            bin_width=self.bin_width,
            bin_number=self.bin_number,
            cropping_distance=self.cropping_distance
        )

        # Then get matrix or matrices
        matrix_list = self._get_matrix(
            image=image,
            mask=mask,
            spatial_method=self.spatial_method
        )

        return matrix_list

    @staticmethod
    @cache
    def _get_matrix(
            image: GenericImage,
            mask: BaseMask,
            spatial_method: str
    ) -> list[MatrixRLM]:
        # Represent image and mask as a dataframe.
        data = mask.as_pandas_dataframe(
            image=image,
            intensity_mask=True
        )

        # Instantiate a helper copy of the current class to be able to use class methods without tying the cache to the
        # instance of the original object from which this method is called.
        matrix_instance = MatrixRLM(
            spatial_method=spatial_method
        )

        # Compute the required matrices.
        matrix_list = [
            matrix.compute(data=data, image_dimenion=image.image_dimension)
            for matrix in matrix_instance.generate(prototype=MatrixRLM, n_slices=image.image_dimension[0])
        ]

        # Merge according to the spatial method.
        matrix_list = matrix_instance.merge(matrix_list, prototype=MatrixRLM)

        # Compute additional values from the individual matrices.
        matrix_list = [matrix.set_values_from_matrix() for matrix in matrix_list]

        return matrix_list

    def clear_cache(self):
        super().clear_cache()
        self._get_matrix.cache_clear()

    def compute(self, image: GenericImage, mask: BaseMask):
        # Compute or retrieve matrices from cache.
        matrices = self.get_matrix(image=image, mask=mask)

        # Compute feature value from matrices, and average over matrices.
        values = [self._compute(matrix=matrix) for matrix in matrices]
        self.value = np.nanmean(values)

    @staticmethod
    def _compute(matrix: MatrixRLM):
        raise NotImplementedError("Implement _compute for feature-specific computation.")


class FeatureRLMSRE(FeatureRLM):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "RLM - short runs emphasis"
        self.abbr_name = "rlm_sre"
        self.ibsi_id = "22OV"
        self.ibsi_compliant = True

    @staticmethod
    def _compute(matrix: MatrixRLM) -> float:
        if matrix.is_empty():
            return np.nan
        return np.sum(matrix.rj.rj / matrix.rj.j ** 2.0) / matrix.n_s


class FeatureRLMLRE(FeatureRLM):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "RLM - long runs emphasis"
        self.abbr_name = "rlm_lre"
        self.ibsi_id = "W4KF"
        self.ibsi_compliant = True

    @staticmethod
    def _compute(matrix: MatrixRLM) -> float:
        if matrix.is_empty():
            return np.nan
        return np.sum(matrix.rj.rj * matrix.rj.j ** 2.0) / matrix.n_s


class FeatureRLMLGRE(FeatureRLM):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "RLM - low grey level run emphasis"
        self.abbr_name = "rlm_lgre"
        self.ibsi_id = "V3SW"
        self.ibsi_compliant = True

    @staticmethod
    def _compute(matrix: MatrixRLM) -> float:
        if matrix.is_empty():
            return np.nan
        return np.sum(matrix.ri.ri ** 2.0) / matrix.n_s


def get_rlm_class_dict() -> dict[str, FeatureRLM]:
    class_dict = {
        "rlm_sre": FeatureRLMSRE,
        "rlm_lre": FeatureRLMLRE,
        "rlm_lgre": FeatureRLMLGRE,
        "rlm_hgre": 4,
        "rlm_srlge": 5,
        "rlm_srhge": 6,
        "rlm_lrlge": 7,
        "rlm_lrhge": 8,
        "rlm_glnu": 9,
        "rlm_glnu_norm": 10,
        "rlm_rlnu": 11,
        "rlm_rlnu_norm": 12,
        "rlm_r_perc": 13,
        "rlm_gl_var": 14,
        "rlm_rl_var": 15,
        "rlm_rl_entr": 16
    }

    return class_dict


def generate_rlm_features(
        settings: FeatureExtractionSettingsClass,
        features: None | list[str]
) -> Generator[FeatureRLM, None, None]:
    class_dict = get_rlm_class_dict()
    rlm_features = set(class_dict.keys())

    # Populate features if available.
    if features is None and settings.has_glrlm_family():
        features = rlm_features

    # Terminate early if no features are set, and none are required.
    if features is None:
        return

    # Select only RLM-features, and return if none are present.
    features = set(features).intersection(rlm_features)
    if len(features) == 0:
        return

    # Features are parametrised by the choice of discretisation parameters and spatial methods..
    for discretisation_parameters in get_discretisation_parameters(
        settings=settings
    ):
        for spatial_method in settings.glrlm_spatial_method:
            for feature in features:
                yield class_dict[feature](
                    spatial_method=spatial_method,
                    **discretisation_parameters
                )
