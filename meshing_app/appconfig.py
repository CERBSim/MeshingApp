from webapp_client import AppConfig, AppAccessConfig
from .version import __version__
from .app import MeshingApp

config = AppConfig(
    name="Meshing App",
    version=__version__,
    python_class=MeshingApp,
    frontend_pip_dependencies=["netgen"],
    frontend_dependencies=[],
    description="Create a mesh from a STEP geometry file. Assign boundary conditions and mesh size interactively. Download the mesh in Netgen format.",
    compute_environments=[],
    access=AppAccessConfig(),
)
