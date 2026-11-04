"""Regression coverage for PEP 639 packaging metadata."""
from pathlib import Path
import re
import unittest


class LicenseMetadataTests(unittest.TestCase):
    def test_license_metadata_uses_pep_639(self):
        text = (Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text(encoding='utf-8')
        sections = dict(re.findall(r'^\[([^\]]+)\]\s*\n(.*?)(?=^\[|\Z)', text, re.M | re.S))
        project = sections['project']
        self.assertRegex(project, r'(?m)^license\s*=\s*"MIT AND CC-BY-4\.0"\s*$')
        self.assertRegex(project, r'(?m)^license-files\s*=\s*\["LICENSE",\s*"LICENSE-docs"\]\s*$')
        self.assertNotRegex(project, r'License ::')
        self.assertNotRegex(sections['tool.setuptools'], r'(?m)^license-files\s*=')
        self.assertIn('setuptools>=77.0.0', sections['build-system'])


if __name__ == '__main__':
    unittest.main()
