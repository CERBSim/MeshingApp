from webapp_client import *
from .version import __version__

class ShapeComponent(Group):
    def __init__(self, id, shape, redraw_command, highlight_color, default_color):
        self.shape = shape
        self.nameParam = StringParameter(id=id + "_name", name="Name",
                                         default=shape.name)
        self.maxh = FloatParameter(id=id + "_maxh", name="Meshsize",
                                   default=shape.maxh)
        self.visibleParam = Switch(id=id + "_visible", name="Visible", default=True)
        super().__init__(id=id, flat=False, horizontal=False,
                         components=[self.nameParam, self.maxh, self.visibleParam])
        self.redraw = redraw_command
        self._selected = False
        self._default_color = default_color
        self._highlight_color = highlight_color
        self._set_color()

    @property
    def selected(self):
        return self._selected

    def _set_color(self):
        if not self.visibleParam.value:
            self._color = (0, 0, 0, 0)
        else:
            if self._selected:
                self._color = self._highlight_color
            else:
                self._color = self._default_color
        if self._id.startswith("solids"):
            if self.visibleParam.value:
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
        id,
        *args,
        redraw_command=None,
        default_color=(0.7, 0.7, 0.7),
        highlight_color=(1, 0, 0),
        **kwargs
    ):
        self.selector = SelectionDialog(id=id + "_sel_group", labels=[], values=[],
                                        variant="dropdown")
        self.selector.on("update", self.on_shape_select)
        self._redraw_command = redraw_command
        self._default_color = default_color
        self._highlight_color = highlight_color
        self._shapes = []
        components = [self.selector]
        super().__init__(id=id, *args, components=components,
                         inline=False, **kwargs)

    def on_shape_select(self):
        selected = self.selector.input.value
        for i, shape in enumerate(self.shape_components):
            shape.selected = i == selected
            self.shape_components[i].dynamic.visible = i == selected
        updateFrontendComponents(self.shape_components)
        self._redraw_command()

    def __getitem__(self, index):
        return self.shape_components[index]

    @property
    def shapes(self):
        return self._shapes

    @shapes.setter
    def shapes(self, shapes):
        self._shapes = shapes
        self.shape_components = []
        labels = []
        values = []
        for i, shape in enumerate(shapes):
            labels.append(self.name[:-1] + " " + str(i) + ("" if not shape.name else " (" + shape.name + ")"))
            values.append(i)
            self.shape_components.append(
                ShapeComponent(
                    id=self._id + "_" + str(i),
                    shape=shape,
                    redraw_command=self._redraw_command,
                    default_color=self._default_color,
                    highlight_color=self._highlight_color,
                )
            )
            self.shape_components[-1].dynamic.visible = False
        self.replace_components([self.selector] + self.shape_components)
        self.selector.dynamic.labels = labels
        self.selector.dynamic.values = values
        self.selector.updateFrontend()


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
        self.generate_mesh_button = Button(id="genmesh", label="Create Mesh",
                                           disabled=True)
        self.download_mesh_button = Button(id="downloadmesh", label="Download Mesh",
                                           disabled=True)
        upload_group = Group(id="upload_group",
                             inline=True,
                             components=[self.geo_upload,
                                         self.generate_mesh_button,
                                         self.download_mesh_button],
                             horizontal=True)
        self.geo = None
        self.webgui = WebguiComponent(
            id="webgui"
        )
        self.webgui2 = WebguiComponent(
            id="webgui2"
        )
        self.webgui2.dynamic.visible=False
        self.webgui.on_click = self.on_webgui_click

        # self.shape_selector = Steps(steps=[self.solids, self.faces, self.edges])
        self.shapetype_selector = SelectionDialog(id="shapetype_selector",
                                                  labels=["Solids",
                                                          "Faces",
                                                          "Edges"],
                                                  value="Faces")
        def select_shape_type():
            self.solids.dynamic.visible = self.shapetype_selector.input.value == "Solids"
            self.faces.dynamic.visible = self.shapetype_selector.input.value == "Faces"
            self.edges.dynamic.visible = self.shapetype_selector.input.value == "Edges"
            updateFrontendComponents([self.solids, self.faces, self.edges])

        self.shapetype_selector.on("update", select_shape_type)
        self.solids = ShapeGroup(id="solid_selector", name="Solids",
                                 visible=False,
                                 redraw_command=self.redraw)
        self.faces = ShapeGroup(id="face_selector", name="Faces",
                                redraw_command=self.redraw)
        self.edges = ShapeGroup(id="edge_selector", name="Edges",
                                visible=False, redraw_command=self.redraw)

        self.shape_selector = Group(id="shape_selector_group",
                                    components=[self.shapetype_selector,
                                                self.solids,
                                                self.faces,
                                                self.edges])

        def load_geo(redraw=True):
            if not self.geo_upload.input.name:
                return
            import os
            name, ext = os.path.splitext(self.geo_upload.input.name[0])
            name = name.split("/")[-1]
            self.input.name = name
            with Loading(self.webgui):
                import netgen.occ as ngocc
                with self.geo_upload as geofile:
                    import os
                    self.geo = ngocc.OCCGeometry(geofile)
                    self.generate_mesh_button.dynamic.disabled = False
                    if redraw:
                        self.redraw()

        def update_geo():
            if not self.geo_upload.input.name:
                return
            with Loading(self.webgui):
                load_geo(redraw=False)
                self.solids.shapes = self.geo.shape.solids
                self.faces.shapes = self.geo.shape.faces
                self.edges.shapes = self.geo.shape.edges
                self.face_neighbours = {face: set() for face in self.geo.shape.faces}
                self.solid_indices = { solid : i for i, solid in enumerate(self.geo.shape.solids) }
                for solid in self.solids.shapes:
                    for face in solid.faces:
                        self.face_neighbours[face].add(solid)
                updateFrontendComponents([self.solids, self.faces, self.edges, self.generate_mesh_button])
                self.redraw()

        self.geo_upload.on("load", load_geo)
        self.geo_upload.on("update", update_geo)
        def do_nothing(*_):
            updateFrontendComponents([])

        self.meshsize = FloatParameter(
            id="meshsize", name="Meshsize", default=None, required=False,
            on_update=do_nothing
        )
        self.curvature = FloatParameter(
            id="curvature", name="Curvature Safety", default=None, required=False,
            on_update=do_nothing
        )

        global_parameters = Group(id="global_parameters",
                                  name="Global Parameters",
                                  title_level=3,
                                  flat=False,
                                  components=[self.meshsize,
                                              self.curvature])

        geo_button = Button(id="geobutton", label="Geometry")
        mesh_button = Button(id="meshbutton", label="Mesh")
        def set_webgui_visible(geo):
            self.webgui.dynamic.visible = geo
            self.webgui2.dynamic.visible = not geo
            updateFrontendComponents([self.webgui, self.webgui2])
        geo_button.on("click", lambda *_: set_webgui_visible(True))
        mesh_button.on("click", lambda *_: set_webgui_visible(False))

        webgui_selector = Group(id="webgui_selector", components=[geo_button, mesh_button], horizontal=True)

        def download_mesh(btn):
            if self.mesh is not None:
                self.mesh.Save("mesh.vol")
                btn.callJSFunction("download", { "filename" : "mesh.vol" })
        self.download_mesh_button.on("click", download_mesh)

        def generate_mesh(btn):
            meshing_pars = {}
            with Loading(self.component):
                if self.meshsize.value is not None:
                    meshing_pars["maxh"] = float(self.meshsize.value)
                self.mesh = self.geo.GenerateMesh(**meshing_pars)
                self.webgui.dynamic.visible=False
                self.webgui2.dynamic.visible=True
                updateFrontendComponents([self.webgui, self.webgui2])
                self.download_mesh_button.dynamic.disabled = False
                self.download_mesh_button.updateFrontend()
                self.webgui2.draw(self.mesh)

        self.generate_mesh_button.on("click", generate_mesh)

        webgui_group = Group(id="webgui_group",
                             components=[webgui_selector, self.webgui, self.webgui2])
        horiz_group = Group(id="horiz_group",
                            components=[self.shape_selector,
                                        webgui_group],
                            horizontal=True)
        self.component = Group(id="main",
                               components=[upload_group,
                                           horiz_group,
                                           global_parameters])

    def on_webgui_click(self, args):
        if args["did_move"]:
            return
        if self.geo is None:
            return
        if not args["ctrlKey"]:
            for f in self.faces.shape_components:
                if f.selected:
                    f.selected = False
            for e in self.edges.shape_components:
                if e.selected:
                    e.selected = False
        if self.shapetype_selector.input.value == "Faces":
            if args["dim"] == 2:
                self.faces.selector.input.value = args["index"]
                self.faces.selector.updateFrontend()
                self.faces[args["index"]].selected = not self.faces[args["index"]].selected
                self.faces.on_shape_select()
        elif self.shapetype_selector.input.value == "Edges":
            if args["dim"] == 1:
                self.edges.selector.input.value = args["index"]
                self.edges.selector.updateFrontend()
                self.edges[args["index"]].selected = not self.edges[args["index"]].selected
        else:
             if args["dim"] == 2:
                one = False
                for solid in self.face_neighbours[self.faces.shapes[args["index"]]]:
                    if self.solids[self.solid_indices[solid]].visible:
                        one = not one
                if one:
                    index = self.solid_indices[solid]
                    self.solids.selector.input.value = index
                    self.solids.selector.updateFrontend()
                    self.solids[index].selected = \
                        not self.solids[index].selected
        self.redraw()

    def redraw(self):
        self.webgui.draw(self.geo.shape)

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"

    def run(self, result_dir):
        pass
