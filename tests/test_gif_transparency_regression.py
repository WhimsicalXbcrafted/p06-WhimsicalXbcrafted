# -*- coding: utf-8 -*-

"""Regression test for GIF transparency loss during resize.

When a paletted GIF with transparency is resized, the transparency
information must be preserved.  This reproduces the issue where
resizing sticker.gif (120×80, P mode with transparency) to 240×160
caused the transparency channel to be lost.
"""

from io import BytesIO
from os.path import abspath, dirname, join
from unittest import TestCase

from PIL import Image

from thumbor.config import Config
from thumbor.context import Context
from thumbor.engines.pil import Engine

STICKER_PATH = abspath(
    join(dirname(__file__), "../course/images/sticker.gif")
)


class GifTransparencyRegressionTestCase(TestCase):
    def get_context(self):
        cfg = Config(
            SECURITY_KEY="ACME-SEC",
            ENGINE="thumbor.engines.pil",
        )
        cfg.STORAGE = "thumbor.storages.no_storage"
        return Context(config=cfg)

    def test_gif_transparency_preserved_after_resize(self):
        """Resizing a paletted GIF with transparency must keep it transparent."""
        context = self.get_context()
        engine = Engine(context)

        with open(STICKER_PATH, "rb") as image_file:
            buffer = image_file.read()

        engine.load(buffer, ".gif")

        # Original image should be paletted with transparency info
        assert engine.original_mode == "P"
        assert "transparency" in engine.image.info

        # Resize to 240×160
        engine.resize(240, 160)

        # Read back as GIF
        result_bytes = BytesIO(engine.read(".gif"))
        resized = Image.open(result_bytes)

        assert resized.format == "GIF"

        # The resized image must still carry transparency info
        assert "transparency" in resized.info, (
            "transparency key lost after resize"
        )

        # At least some pixels must be transparent (not fully opaque)
        alpha = resized.convert("RGBA").split()[3]
        transparent_count = sum(
            alpha.point(lambda x: 0 if x == 0 else 1).getdata()
        )
        assert transparent_count > 0, (
            "no transparent pixels found after resize – transparency was lost"
        )
