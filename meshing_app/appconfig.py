from webapp_client import AppConfig, AppAccessConfig
from .version import __version__
from .app import MeshingApp

config = AppConfig(
    name="Meshing App",
    version=__version__,
    python_class=MeshingApp,
    frontend_pip_dependencies=["netgen"],
    frontend_dependencies=[],
    description="A simple meshing app",
    compute_environments=[],
    access=AppAccessConfig(),
)
