import io

import pytest
from PIL import Image

from crabgraph.multimodal import image_content
from crabgraph.pond import analyze_csv


def test_pond_statistics_ignore_invalid_and_nonfinite_values():
    result = analyze_csv("date,ph,dissolved_oxygen\n1,7.8,5.8\n2,8,NaN\n3,bad,4.8\n")
    assert result["metrics"]["ph"]["mean"] == 7.9
    assert result["metrics"]["dissolved_oxygen"]["change"] == -1.0
    assert result["invalid_values"] == 2


def test_rejects_missing_measurement_columns():
    with pytest.raises(ValueError):
        analyze_csv("note\nhello\n")


def test_image_validation_uses_actual_format():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color="gray").save(buffer, format="PNG")
    assert image_content(buffer.getvalue())["image_url"]["url"].startswith("data:image/png;base64,")
    with pytest.raises(Exception):
        image_content(b"not a png")


def test_image_size_limit_is_enforced():
    with pytest.raises(ValueError, match="8 MB"):
        image_content(b"x" * (8 * 1024**2 + 1))
