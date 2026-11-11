# -*- coding: utf-8 -*-

# Regression test for Issue #2: transparent rounded corners carry a dark ring.
#
# When round_corner is called with transparent=True, anti-aliased edge pixels
# must keep their original color and fade to full transparency via the alpha
# channel.  The buggy code darkens RGB toward black and sets alpha=0 instead.
#
# This test builds a 100x100 solid-blue source image, applies
# round_corner(25, 255, 255, 255, transparent=True), and checks that an
# anti-aliased edge pixel near the top-left corner keeps its blue channel at
# 255 (the original color) with partial alpha.  If the bug is present, the
# blue channel will be darkened (e.g., 27 instead of 255) and alpha will be 0.

from io import BytesIO

import pytest
from PIL import Image
from tornado.testing import gen_test

from tests.base import FilterTestCase
from thumbor.config import Config
from thumbor.context import Context, RequestParameters
from thumbor.importer import Importer
from thumbor.transformer import Transformer


class RoundCornerTransparentRegressionTestCase(FilterTestCase):
    """Regression test for transparent rounded-corner dark ring (Issue #2)."""

    def _make_source(self, color):
        """Return a BytesIO containing a 100x100 solid-color PNG."""
        source = Image.new("RGBA", (100, 100), color)
        buf = BytesIO()
        source.save(buf, "PNG")
        buf.seek(0)
        return buf

    @gen_test
    async def test_round_corner_transparent_blue_channel_not_darkened(self):
        """Edge pixels must keep original RGB; only alpha fades to 0."""
        config = Config(
            FILTERS=["thumbor.filters.round_corner"],
            LOADER="thumbor.loaders.file_loader",
            FILE_LOADER_ROOT_PATH=self.get_fixture_root_path(),
        )
        importer = Importer(config)
        importer.import_modules()

        req = RequestParameters()
        context = Context(config=config, importer=importer)
        context.request = req
        context.request.engine = context.modules.engine

        buf = self._make_source((0, 0, 255, 255))
        context.modules.engine.load(buf.getvalue(), ".png")

        fltr = importer.filters[0](
            "round_corner(25,255,255,255,1)", context=context
        )
        fltr.pre_compile()
        context.transformer = Transformer(context)
        await fltr.run()

        result_image = fltr.engine.image.convert("RGBA")

        # Pixel (18, 0) is on the anti-aliased edge of the top-left corner.
        # The source is solid blue (0, 0, 255).  With transparent=True the
        # edge pixel must keep its blue channel at 255 and have partial alpha.
        pixel = result_image.getpixel((18, 0))
        r, g, b, a = pixel

        assert b == 255, (
            f"Blue channel at edge pixel (18,0) is {b}, expected 255. "
            f"Full pixel: {pixel}. The transparent corner darkens RGB toward black."
        )
        assert 0 < a < 255, (
            f"Alpha at edge pixel (18,0) is {a}, expected between 0 and 255. "
            f"Full pixel: {pixel}."
        )

    @gen_test
    async def test_round_corner_transparent_green_channel_not_darkened(self):
        """Corner edge pixels keep source color, not fill color or black."""
        config = Config(
            FILTERS=["thumbor.filters.round_corner"],
            LOADER="thumbor.loaders.file_loader",
            FILE_LOADER_ROOT_PATH=self.get_fixture_root_path(),
        )
        importer = Importer(config)
        importer.import_modules()

        req = RequestParameters()
        context = Context(config=config, importer=importer)
        context.request = req
        context.request.engine = context.modules.engine

        buf = self._make_source((0, 255, 0, 255))
        context.modules.engine.load(buf.getvalue(), ".png")

        fltr = importer.filters[0](
            "round_corner(25,255,255,255,1)", context=context
        )
        fltr.pre_compile()
        context.transformer = Transformer(context)
        await fltr.run()

        result_image = fltr.engine.image.convert("RGBA")

        pixel = result_image.getpixel((16, 1))
        r, g, b, a = pixel

        # Source is solid green (0, 255, 0).
        assert g == 255, (
            f"Green channel at edge pixel (16,1) is {g}, expected 255. "
            f"Full pixel: {pixel}. The transparent corner darkens RGB toward black."
        )
        assert 0 < a < 255, (
            f"Alpha at edge pixel (16,1) is {a}, expected between 0 and 255. "
            f"Full pixel: {pixel}."
        )
