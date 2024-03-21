from webapp_client import (
    BaseModel,
    Group,
    register_application,
    FileInput,
    Loading,
    WebguiComponent,
    FloatParameter,
    StringParameter,
    Switch,
    Steps,
    updateFrontendComponents,
    Button,
    SelectionDialog
)
from .version import __version__

class ShapeComponent(Group):
    def __init__(self, id, shape, redraw_command, highlight_color, default_color):
        super().__init__(id=id, flat=False, horizontal=True)
        self.shape = shape
        self.name = StringParameter(id=id + "_name", name="Name", default=shape.name)
        self.maxh = FloatParameter(id=id + "_maxh", name="Meshsize", default=shape.maxh)
        self.visible = Switch(id=id + "_visible", name="Visible", default=True)
        self.redraw = redraw_command
        self._selected = False
        self._visible = True
        self._default_color = default_color
        self._highlight_color = highlight_color
        self._set_color()

    @property
    def selected(self):
        return self._selected

    def _set_color(self):
        if not self._visible:
            self._color = (0, 0, 0, 0)
        else:
            if self._selected:
                self._color = self._highlight_color
            else:
                self._color = self._default_color
        if self._id.startswith("solids"):
            if self.visible:
                self.shape.faces.col = self._color
        else:
            self.shape.col = self._color

    @selected.setter
    def selected(self, selected):
        self._selected = selected
        self._set_color()

class ShapeGroup(Group):
    def __init__(
        self,
        *args,
        redraw_command=None,
        default_color=(0, 0, 0),
        highlight_color=(1, 0, 0),
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._redraw_command = redraw_command
        self._default_color = default_color
        self._highlight_color = highlight_color
        self._shapes = []

    def __getitem__(self, index):
        return self.components[index]

    @property
    def shapes(self):
        return self._shapes

    @shapes.setter
    def shapes(self, shapes):
        self._shapes = shapes
        self.shape_components = []
        for i, shape in enumerate(shapes):
            self.shape_components.append(
                ShapeComponent(
                    id=self._id + "_" + str(i),
                    shape=shape,
                    redraw_command=self._redraw_command,
                    default_color=self._default_color,
                    highlight_color=self._highlight_color,
                )
            )
        self.components = self.shape_components


@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = "default"
    frontend_pip_dependencies = ["netgen"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_upload = FileInput(
            id="geo_file", label="Geometry Upload", extensions="step,stp,brep"
        )
        self.geo = None
        self.webgui = WebguiComponent(
            id="webgui", initial_load=False, enable_sidebar=False
        )
        self.webgui2 = WebguiComponent(
            id="webgui2", initial_load=False, enable_sidebar=False
        )
        self.webgui2.dynamic.visible=False
        self.webgui.on("click", self.on_webgui_click)
        self.solids = ShapeGroup(id="solids", name="Solids")
        self.faces = ShapeGroup(
            id="faces",
            name="Faces",
            default_color=(0.7, 0.7, 0.7),
            redraw_command=self.redraw,
        )
        self.edges = ShapeGroup(
            id="edges",
            name="Edges",
            default_color=(0, 0, 0),
            redraw_command=self.redraw)
        self.active_step = "solids"
        # self.shape_selector = Steps(steps=[self.solids, self.faces, self.edges])
        self.shape_selector = SelectionDialog(id="shape_selector",
                                              labels=["Solids", "Faces", "Edges"],
                                              value="Faces")
                                              
        def update_active_step(val):
            print("update active step, val = ", val.dynamic.value)

        # self.shape_selector.on("update", update_active_step)

        def draw_geo(comp):
            print("draw geo")
            if not self.geo_upload.input.name:
                return
            with Loading(self.webgui):
                import netgen.occ as ngocc

                with self.geo_upload as geofile:
                    print("geofile = ", geofile)
                    self.geo = ngocc.OCCGeometry(geofile)
                    self.solids.shapes = self.geo.shape.solids
                    self.faces.shapes = self.geo.shape.faces
                    self.edges.shapes = self.geo.shape.edges
                    self.generate_mesh_button.dynamic.disabled = False
                    updateFrontendComponents([self.solids, self.faces, self.edges, self.generate_mesh_button])
                    self.redraw()

        self.geo_upload.on("load", draw_geo)
        self.geo_upload.on("update", draw_geo)
        def do_nothing(*_):
            updateFrontendComponents([])
        self.meshsize = FloatParameter(
            id="meshsize", name="Meshsize", default=None, required=False,
            on_update=do_nothing
        )

        geo_button = Button(id="geobutton", label="Geometry")
        mesh_button = Button(id="meshbutton", label="Mesh")
        def set_webgui_visible(geo):
            self.webgui.dynamic.visible = geo
            self.webgui2.dynamic.visible = not geo
            updateFrontendComponents([self.webgui, self.webgui2])
        geo_button.on("click", lambda *_: set_webgui_visible(True))
        mesh_button.on("click", lambda *_: set_webgui_visible(False))

        webgui_selector = Group(id="webgui_selector", components=[geo_button, mesh_button], horizontal=True)

        self.generate_mesh_button = Button(id="genmesh", label="Create Mesh",
                                           disabled=True)
        self.save_mesh_button = Button(id="savemesh", label="Save Mesh",
                                       disabled=True)
        def generate_mesh(btn):
            meshing_pars = {}
            with Loading(self.component):
                if self.meshsize.value is not None:
                    meshing_pars["maxh"] = float(self.meshsize.value)
                self.mesh = self.geo.GenerateMesh(**meshing_pars)
                self.webgui.dynamic.visible=False
                self.webgui2.dynamic.visible=True
                updateFrontendComponents([self.webgui, self.webgui2])
                self.webgui2.draw(self.mesh)

        self.generate_mesh_button.on("click", generate_mesh)

        meshing_parameters = Group(id="meshing_parameters",
                                   components=[self.meshsize,
                                               self.generate_mesh_button])

        webgui_group = Group(id="webgui_group",
                             components=[webgui_selector, self.webgui, self.webgui2])
        horiz_group = Group(id="horiz_group",
                            components=[self.shape_selector,
                                        webgui_group],
                            horizontal=True)
        self.component = Group(id="main",
                               components=[self.geo_upload,
                                           horiz_group,
                                           meshing_parameters])

    def on_webgui_click(self, args):
        if args["did_move"]:
            return
        if self.geo is None:
            return
        if not args["ctrlKey"]:
            for f in self.faces.components:
                if f.selected:
                    f.selected = False
            for e in self.edges.components:
                if e.selected:
                    e.selected = False
        if args["dim"] == 2:
            self.faces[args["index"]].selected = not self.faces[args["index"]].selected
        if args["dim"] == 1:
            self.edges[args["index"]].selected = not self.edges[args["index"]].selected
        self.redraw()

    def redraw(self):
        self.webgui.draw(self.geo.shape)

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"

    def run(self, result_dir):
        pass
