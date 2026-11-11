# -*- coding: utf-8 -*-

# Regression test for Issue #4: extreme aspect-ratio crop produces empty image.
#
# In `thumbor/transformer.py`, `auto_crop()` computes:
#
#     crop_height = int(round(source_width * self.target_height / target_width, 0))
#
# For a 1x1 source resized to 50x25 this gives round(0.5) = 0 (Python
# banker's rounding), so the image is cropped to (0, 0, 1, 0) -- an empty
# 1x0 image.  PIL's resize() on an empty image produces all-(0,0,0,0)
# pixels, which is exactly the "image disappears" symptom.
#
# The fix clamps crop_width and crop_height to at least 1 after the math.

from io import BytesIO

import pytest
from PIL import Image
from tornado.testing import gen_test

from tests.base import FilterTestCase
from thumbor.config import Config
from thumbor.context import Context, RequestParameters
from thumbor.importer import Importer
from thumbor.transformer import Transformer


class ExtremeAspectCropRegressionTestCase(FilterTestCase):
    """Regression test for extreme aspect-ratio crop (Issue #4)."""

    def _make_source(self, width, height, color=(255, 0, 0, 255)):
        """Return a BytesIO containing a solid-color PNG."""
        source = Image.new("RGBA", (width, height), color)
        buf = BytesIO()
        source.save(buf, "PNG")
        buf.seek(0)
        return buf

    def _transform(self, source_buf, width=None, height=None, fit_in=False):
        """Run the full transform pipeline and return the result image."""
        config = Config(
            FILTERS=[],
            LOADER="thumbor.loaders.file_loader",
            FILE_LOADER_ROOT_PATH=self.get_fixture_root_path(),
        )
        importer = Importer(config)
        importer.import_modules()

        req = RequestParameters(fit_in=fit_in)
        context = Context(config=config, importer=importer)
        context.request = req
        context.request.engine = context.modules.engine

        context.modules.engine.load(source_buf.getvalue(), ".png")

        trans = Transformer(context)
        if width is not None:
            context.request.width = width
        if height is not None:
            context.request.height = height
        trans.img_operation_worker()

        return context.modules.engine.image

    @gen_test
    async def test_crop_height_not_zero_50x25_from_1x1(self):
        """1x1 source -> 50x25 must produce a valid non-empty image."""
        buf = self._make_source(1, 1, (255, 0, 0, 255))
        result = self._transform(buf, width=50, height=25)

        w, h = result.size
        assert w == 50, f"Expected width 50, got {w}"
        assert h == 25, f"Expected height 25, got {h}"

        # The image must not be all-transparent (alpha=0 everywhere)
        rgba = result.convert("RGBA")
        has_color = False
        for x in range(w):
            for y in range(h):
                r, g, b, a = rgba.getpixel((x, y))
                if r > 0 or g > 0 or b > 0 or a > 0:
                    has_color = True
                    break
            if has_color:
                break
        assert has_color, (
            "Result image is entirely transparent -- auto_crop produced an empty crop."
        )

    @gen_test
    async def test_crop_width_not_zero_1x1_from_500x500(self):
        """500x500 source -> 1x1 via fit-in must return a 1x1 image."""
        buf = self._make_source(500, 500, (0, 255, 0, 255))
        result = self._transform(buf, width=1, height=1, fit_in=True)

        w, h = result.size
        assert w == 1, f"Expected width 1, got {w}"
        assert h == 1, f"Expected height 1, got {h}"

        rgba = result.convert("RGBA")
        r, g, b, a = rgba.getpixel((0, 0))
        assert g > 0, (
            f"Pixel should be green but is ({r},{g},{b},{a}). "
            "auto_crop produced an empty crop."
        )

    @gen_test
    async def test_crop_dimension_at_least_one(self):
        """auto_crop must never produce a zero-dimension crop box."""
        buf = self._make_source(1, 1, (255, 255, 0, 255))
        result = self._transform(buf, width=50, height=25)

        w, h = result.size
        assert w >= 1, f"Width must be >= 1, got {w}"
        assert h >= 1, f"Height must be >= 1, got {h}"
