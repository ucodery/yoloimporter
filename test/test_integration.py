import sys
import unittest
from importlib import reload

class TestPypiImport(unittest.TestCase):
    # NOTE: none of the test imports can be part of this package's requirements
    # (including transitive and test)

    @classmethod
    def setUpClass(cls):
        cls.startup_meta_path = sys.meta_path.copy()
        import yoloimport
        cls.yolo_meta_path = sys.meta_path.copy()

    @classmethod
    def yolo(cls):
        sys.meta_path = cls.yolo_meta_path.copy()

    def setUp(self):
        sys.meta_path = self.startup_meta_path.copy()

    def test_module(self):
        """Test importing a single-module project"""
        # note: no transitive dependencies
        # package name: q
        # project name: q
        with self.assertRaises(ImportError):
            import q

        self.yolo()
        import q
        q.q

    def test_package(self):
        """Test importing a package with modules of depth 1"""
        # note: no transitive dependencies
        # package name: more_itertools
        # project name: more-itertools
        with self.assertRaises(ImportError):
            import more_itertools

        self.yolo()
        import more_itertools
        self.assertTrue(hasattr(more_itertools, "more"))
        self.assertIsInstance(more_itertools.more, type(more_itertools))

    def test_deep_package(self):
        """Test importing a package containing sub packages"""
        # note: no transitive dependencies
        # package name: pygments
        # project name: Pygments
        with self.assertRaises(ImportError):
            import pygments

        self.yolo()
        import pygments
        import pygments.styles
        import pygments.styles.default
        self.assertIsInstance(pygments.styles, type(pygments))
        self.assertIsInstance(pygments.styles.default, type(pygments))

    def test_package_with_dependencies(self):
        """Test importing a package that has other, unfulfilled, dependencies"""
        # package name: virtualenv
        # project name: virtualenv
        with self.assertRaises(ImportError):
            import virtualenv
        with self.assertRaises(ImportError):
            import platformdirs

        self.yolo()
        import virtualenv
        self.assertIn("platformdirs", sys.modules)
        import platformdirs

    def test_reload(self):
        self.yolo()

        import slicetime
        original = slicetime.__doc__
        slicetime.__doc__ = "Just a test"

        reload(slicetime)
        self.assertEqual(slicetime.__doc__, original)

    def test_non_normalized_package(self):
        """pypi.org namespace is normalized (including case-insensitive)
        while interpreter module cache is non-normalized (case-sensitive).
        Don't locate pypi packages that match a normalized version of the
        package, as then the same package could exist multiple times at once
        """
        self.yolo()

        with self.assertRaises(ImportError):
            import Q



if __name__ == "__main__":
    unittest.main()
