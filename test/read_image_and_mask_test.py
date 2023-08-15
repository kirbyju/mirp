import os.path
import pytest

from mirp.importData.importImageAndMask import import_image_and_mask
from mirp.importData.readData import read_image_and_masks
from mirp.imageClass import ImageClass
from mirp.roiClass import RoiClass


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


def test_read_itk_image_and_mask():
    # Simple test.
    image_list = import_image_and_mask(
        image=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "image", "image.nii.gz"),
        mask=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "mask", "mask.nii.gz")
    )

    image, roi_list = read_image_and_masks(image=image_list[0])
    assert isinstance(image, ImageClass)
    assert len(roi_list) == 1
    assert all(isinstance(roi, RoiClass) for roi in roi_list)

    # With roi name specified.
    image_list = import_image_and_mask(
        image=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "image", "image.nii.gz"),
        mask=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "mask", "mask.nii.gz"),
        roi_name="1"
    )

    image, roi_list = read_image_and_masks(image=image_list[0])
    assert isinstance(image, ImageClass)
    assert len(roi_list) == 1
    assert all(isinstance(roi, RoiClass) for roi in roi_list)

    # With roi name not appearing.
    image_list = import_image_and_mask(
        image=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "image", "image.nii.gz"),
        mask=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "mask", "mask.nii.gz"),
        roi_name="2"
    )

    image, roi_list = read_image_and_masks(image=image_list[0])
    assert isinstance(image, ImageClass)
    assert len(roi_list) == 0

    # Multiple roi names of which one is present.
    image_list = import_image_and_mask(
        image=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "image", "image.nii.gz"),
        mask=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "mask", "mask.nii.gz"),
        roi_name=["1", "2", "3"]
    )

    image, roi_list = read_image_and_masks(image=image_list[0])
    assert isinstance(image, ImageClass)
    assert len(roi_list) == 1
    assert all(isinstance(roi, RoiClass) for roi in roi_list)

    # Multiple roi names, with dictionary to set labels.
    image_list = import_image_and_mask(
        image=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "image", "image.nii.gz"),
        mask=os.path.join(CURRENT_DIR, "data", "sts_images", "STS_001", "CT", "nifti", "mask", "mask.nii.gz"),
        roi_name={"1": "gtv", "2": "some_roi", "3": "another_roi"}
    )

    image, roi_list = read_image_and_masks(image=image_list[0])
    assert isinstance(image, ImageClass)
    assert len(roi_list) == 1
    assert all(isinstance(roi, RoiClass) for roi in roi_list)
    assert roi_list[0].name == "gtv"


