
from webapp_client import (
    BaseModel,
    Group,
    register_application,
    FileInput,
    Loading,
    WebguiComponent,
    FloatParameter,
    Switch
)
from .version import __version__

async def installModules():
    try:
        import netgen
    except:
        import webapp_frontend
        await webapp_frontend.installModule("netgen")

@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = "default"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_upload = FileInput(id="geo_file", label="Geometry Upload",
                                     extensions="step,stp,brep")
        self.geo = None
        self.webgui = WebguiComponent(id="webgui",
                                      initial_load=False, enable_sidebar=False)
        self.webgui.on_click = self.on_webgui_click
        self._clicked_faces = set()
        self._clicked_edges = set()

        async def draw_geo(comp):
            if not self.geo_upload.data:
                return
            async with Loading(self.webgui):
                await installModules()
                import netgen.occ as ngocc
                with self.geo_upload as geofile:
                    self.geo = ngocc.OCCGeometry(geofile)
                    self.faces = self.geo.shape.faces
                    self.edges = self.geo.shape.edges
                    await self.redraw()

        self.geo_upload.on_load = draw_geo
        self.geo_upload.on_update = draw_geo

        self.meshsize = FloatParameter(id="meshsize",
                                       name="Meshsize",
                                       default=None,
                                       required=False)
        generate_mesh_button = Switch(id="genmesh", name="Create Mesh",
                                      default=False)
        async def generate_mesh(comp):
            meshing_pars = {}
            print("call generate mesh")
            if self.meshsize.value is not None:
                meshing_pars["maxh"] = float(self.meshsize.value)
            self.mesh = self.geo.GenerateMesh(**meshing_pars)
            await self.webgui.draw(self.mesh)

        generate_mesh_button.on_update = generate_mesh

        meshing_parameters = Group(id="meshing_parameters",
                                   components=[self.meshsize,
                                               generate_mesh_button])

        horiz_group = Group(id="horiz_group",
                            components=[self.webgui,
                                        meshing_parameters],
                            horizontal=True)
        
        self.component = Group(id="main",
                               components=[self.geo_upload,
                                           horiz_group])

    async def on_webgui_click(self, args):
        print("on click args", args)
        if args["did_move"]:
            return
        if self.geo is None:
            return
        if not args["ctrlKey"]:
            self._clicked_edges = set()
            self._clicked_faces = set()
        if args["dim"] == 2:
            if args["index"] in self._clicked_faces:
                self._clicked_faces.remove(args["index"])
            else:
                self._clicked_faces.add(args["index"])
        if args["dim"] == 1:
            if args["index"] in self._clicked_edges:
                self._clicked_edges.remove(args["index"])
            else:
                self._clicked_edges.add(args["index"])
        await self.redraw()

    async def redraw(self):
        self.faces.col = (0.7, 0.7, 0.7)
        self.edges.col = (0, 0, 0)
        for face in self._clicked_faces:
            self.faces[face].col = (1, 0, 0)
        for edge in self._clicked_edges:
            self.edges[edge].col = (1, 0, 0)
        await self.webgui.draw(self.geo.shape)


    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"

    def run(self, result_dir):
        pass
