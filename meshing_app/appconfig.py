from webapp_client import AppConfig, AppAccessConfig, AccessLevel
from .version import __version__
from .app import MeshingApp
from webapp_client.utils import load_image
import os

config = AppConfig(
    name="Meshing App",
    version=__version__,
    python_class=MeshingApp,
    frontend_pip_dependencies=["netgen"],
    frontend_dependencies=[],
    image=load_image(os.path.join(
        os.path.dirname(__file__),"assets/app_image.png")),
    description="Create a mesh from a STEP geometry file. Assign boundary conditions and mesh size interactively. Download the mesh in Netgen format.",
    compute_environments=[],
    access=AppAccessConfig(default_level = AccessLevel.STANDARD),
)
