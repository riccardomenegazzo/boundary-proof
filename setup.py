from pathlib import Path
from shutil import copytree
from setuptools import setup
from setuptools.command.build_py import build_py

class BuildWithDashboard(build_py):
    def run(self):
        super().run()
        copytree(Path(__file__).parent/'dist',Path(self.build_lib)/'boundary_proof'/'dashboard',dirs_exist_ok=True)

setup(cmdclass={'build_py':BuildWithDashboard})
