from webapp_client import *
from webapp_client.components import Row, Col, Div
from webapp_client.qcomponents import *
from .version import __version__

btn_style = "margin: 1px; padding: 5px;"

class UserWarning(QDialog):
    def __init__(self, title, message):
        card = QCard(
            children=[QCardSection(children=Div(classes="text-h6",
                                                style="color: warning;",
                                                children=title)),
                      QCardSection(classes="q-pt-none",
                                   children=message),
                      QCardActions(align="right",
                                   children=QBtn(
                                       flat=True,
                                       label="Ok",
                                       color="primary").on_click(self.close))])
        super().__init__(children=card)

    def close(self):
        self.model_value = False
        self.update_frontend()

class FileUpload(QFile):
    def __init__(self, app, id=None, error_title="Error in File Upload",
                 error_text="Please upload a valid file", **kwargs):
        style = kwargs.get("style", { "height": "100px",
                                      "border": "1px solid rgba(60, 190, 242, 1)",
                                      "border-radius": "15px",
                                      "background-color": "rgba(60, 190, 242, .2)",
                                      "margin-top": "30px",
                                      "margin-bottom": "70px",
                                      "padding": "20px",
                                      "border-style": "dashed",
                                      "max-width": "400px"})
        super().__init__(id=id, style=style, **kwargs)
        self.app = app
        self.user_warning = UserWarning(title=error_title, message=error_text)
        self.slot_prepend = [QIcon(name="upload"), self.user_warning]
        self.on_update_model_value(self.read_file)
        self.on_clear(self.clear_file)
        self.filename = None
        self.file_data = None
        self.on_rejected(self.show_warning)
        self.on_file_loaded_callbacks = []

    def clear_file(self):
        self.filename = None
        self.file_data = None

    def read_file(self):
        self.filename = self.model_value.name
        self.model_value.arrayBuffer().then(self.set_file_data)

    def set_file_data(self, arraybuffer):
        self.file_data = arraybuffer.to_bytes()
        for callback in self.on_file_loaded_callbacks:
            callback()

    def dump(self):
        print(dir(self.model_value))
        if self.file_data is not None:
            self.app._store_data_file(self.file_data.decode(), self.filename)
        return { "filename": self.filename, }
                 # "filedata": self.file_data }

    def load(self, data):
        self.filename = data["filename"]
        if self.filename is not None:
            self.file_data = self.app._load_data_file(self.filename).encode()
        print("model value = ", self.model_value)

    def show_warning(self):
        self.user_warning.model_value = True
        self.user_warning.update_frontend()

    def __enter__(self) -> list[str] | str:
        # Create a temporary file storing the data
        import tempfile, os
        self.tmpdir = tempfile.TemporaryDirectory()
        tmp_path = self.tmpdir.__enter__()
        if isinstance(self.file_data, bytes):
            file_path = os.path.join(tmp_path, self.filename)
            with open(file_path, "wb") as file:
                file.write(self.file_data)
            return file_path

        file_paths = []
        data_items = copy.deepcopy(self.data)
        for file_name, data in data_items.items():
            if file_name.endswith(".zip"):
                import base64
                import io
                import zipfile

                byte_stream = io.BytesIO(base64.b64decode(data))
                with zipfile.ZipFile(byte_stream, "r") as zip_ref:
                    zip_ref.extractall(tmp_path)
                    extracted_file_names = zip_ref.namelist()
                    for extracted_file_name in extracted_file_names:
                        file_path = os.path.join(tmp_path, extracted_file_name)
                        with open(file_path, "r", encoding="utf-8") as file:
                            data = file.read()
                        self.data[extracted_file_name] = data
                        self._state.name.append(extracted_file_name)
                        file_paths.append(file_path)

                # Remove the zip file from the data
                del self._state.data[file_name]
                self._state.name.remove(file_name)
            else:
                file_path = os.path.join(tmp_path, file_name)
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(data)
                file_paths.append(file_path)
        return file_paths if len(file_paths) > 1 else file_paths[0]

    def __exit__(self, *args, **kwargs):
        self.tmpdir.__exit__(*args, **kwargs)

        

class ShapeComponent(QItem):
    def __init__(self, id, shape):
        self.nameParam = QInput(
            id=id + "_name", label="Name",
            model_value=shape.name,
            debounce=200,
            style="min-width: 200px").on_update_model_value(self.set_name)
        self.maxh = QInput(id=id + "_maxh", label="Meshsize",
                           type="number",
                           debounce=200,
                           model_value=shape.maxh if shape.maxh < 1e98 else None
                           ).on_update_model_value(self.set_maxh)
        super().__init__(children=Row([QItemSection(children=c) for c in [self.nameParam, self.maxh]]))
        self._shape = shape

    def set_name(self, name):
        self._shape.name = name

    def set_maxh(self, maxh):
        self._shape.maxh = maxh
        

class ShapeGroup(DynamicGroup):
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
                                        variant="dropdown",
                                        )
        self.selector.dynamic.label = "Select " + kwargs["name"]
        self.selector.dynamic.style = "width: 400px"
        self.selector.on("update", self.on_shape_select)
        self._redraw_command = redraw_command
        self._default_color = default_color
        self._highlight_color = highlight_color
        self._shapes = []
        components = [self.selector]
        super().__init__(id=id, *args, components=components,
                         inline=True, **kwargs)

    @property
    def shape_components(self):
        return self.components[1:]

    def on_shape_select(self):
        print("on_shape_select, ", self.selector.value)
        selected = self.selector.input.value
        for i, shape in enumerate(self.shape_components):
            shape.selected = i == selected
            shape.dynamic.visible = i == selected
        updateFrontendComponents(self.components)
        self._redraw_command()

    def __getitem__(self, index):
        return self.shape_components[index]

    @property
    def shapes(self):
        return self._shapes

    @shapes.setter
    def shapes(self, shapes):
        self._shapes = shapes
        shape_components = []
        labels = []
        values = []
        for i, shape in enumerate(shapes):
            labels.append(self.name[:-1] + " " + str(i) + ("" if not shape.name else " (" + shape.name + ")"))
            values.append(i)
            shape_components.append(
                ShapeComponent(
                    id=self._id + "_" + str(i),
                    shape=shape,
                    redraw_command=self._redraw_command,
                    default_color=self._default_color,
                    highlight_color=self._highlight_color,
                )
            )
            shape_components[-1].dynamic.visible = False
        self.replace_components([self.selector] + shape_components)
        self.selector.dynamic.labels = labels
        self.selector.dynamic.values = values
        self.selector.updateFrontend()

@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = "default"
    canRun = False
    frontend_pip_dependencies = ["netgen"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo = None
        self.create_layout()

        # self.geo = None
        # webgui_settings = {
        #     "Light": {"specularity": 0},
        #     "Misc": {"line_thickness": 1},
        #     "Objects": {"Edges": True, "Axes": False},
        # }
        # self.webgui = WebguiComponent(
        #     id="webgui", settings=webgui_settings,
        # )
        # self.webgui2 = WebguiComponent(
        #     id="webgui2", settings=webgui_settings
        # )
        # self.dimensions_label = Label(id="dimensions_label", label="Dimensions:")
        # self.webgui2.dynamic.visible=False
        # self.webgui.on_click = self.on_webgui_click

        # # self.shape_selector = Steps(steps=[self.solids, self.faces, self.edges])
        # self.shapetype_selector = SelectionDialog(id="shapetype_selector",
        #                                           labels=["Solids",
        #                                                   "Faces",
        #                                                   "Edges"],
        #                                           value="Faces")
        # self.shapetype_selector.dynamic.style = "margin: 10px"
        # def select_shape_type():
        #     print("select shape type = ", self.shapetype_selector.value)
        #     self.solids.dynamic.visible = self.shapetype_selector.input.value == "Solids"
        #     self.faces.dynamic.visible = self.shapetype_selector.input.value == "Faces"
        #     self.edges.dynamic.visible = self.shapetype_selector.input.value == "Edges"
        #     updateFrontendComponents([self.solids, self.faces, self.edges])

        # self.shapetype_selector.on("update", select_shape_type)
        # self.solids = ShapeGroup(id="solid_selector", name="Solids",
        #                          visible=False,
        #                          redraw_command=self.redraw)
        # self.faces = ShapeGroup(id="face_selector", name="Faces",
        #                         redraw_command=self.redraw)
        # self.edges = ShapeGroup(id="edge_selector", name="Edges",
        #                         visible=False, redraw_command=self.redraw)

        # self.shape_selector = Group(id="shape_selector_group",
        #                             components=[self.shapetype_selector,
        #                                         self.solids,
        #                                         self.faces,
        #                                         self.edges])

        # def load_geo(redraw=True):
        #     if not self.geo_upload.input.name:
        #         return
        #     import os
        #     name, ext = os.path.splitext(self.geo_upload.input.name[0])
        #     name = name.split("/")[-1]
        #     self.input.name = name
        #     with Loading(self.webgui):
        #         import netgen.occ as ngocc
        #         with self.geo_upload as geofile:
        #             import os
        #             self.geo = ngocc.OCCGeometry(geofile)
        #             self.original_geo = ngocc.OCCGeometry(self.geo.shape,
        #                                                   copy=True)
        #             self.generate_mesh_button.dynamic.disabled = False
        #             if redraw:
        #                 self.redraw()

        # def update_geo():
        #     if not self.geo_upload.input.name:
        #         return
        #     with Loading(self.webgui):
        #         load_geo(redraw=False)
        #         self.solids.shapes = self.geo.shape.solids
        #         self.faces.shapes = self.geo.shape.faces
        #         self.edges.shapes = self.geo.shape.edges
        #         self.face_neighbours = {face: set() for face in self.geo.shape.faces}
        #         self.solid_indices = { solid : i for i, solid in enumerate(self.geo.shape.solids) }
        #         for solid in self.solids.shapes:
        #             for face in solid.faces:
        #                 self.face_neighbours[face].add(solid)
        #         updateFrontendComponents([self.solids, self.faces, self.edges, self.generate_mesh_button])
        #         self.redraw()

        # self.geo_upload.on("load", load_geo)
        # self.geo_upload.on("update", update_geo)
        # def do_nothing(*_):
        #     updateFrontendComponents([])

        # self.meshsize = FloatParameter(
        #     id="meshsize", name="Meshsize", default=None, required=False,
        #     on_update=do_nothing
        # )
        # self.curvature = FloatParameter(
        #     id="curvature", name="Curvature Safety", default=None, required=False,
        #     on_update=do_nothing
        # )

        # global_parameters = Group(id="global_parameters",
        #                           name="Global Parameters",
        #                           title_level=3,
        #                           flat=False,
        #                           components=[self.meshsize,
        #                                       self.curvature])

        # geo_button = Button(id="geobutton", label="Geometry", style=btn_style)
        # mesh_button = Button(id="meshbutton", label="Mesh", style=btn_style)
        # def set_webgui_visible(geo):
        #     self.webgui.dynamic.visible = geo
        #     self.webgui2.dynamic.visible = not geo
        #     updateFrontendComponents([self.webgui, self.webgui2])
        # geo_button.on("click", lambda *_: set_webgui_visible(True))
        # mesh_button.on("click", lambda *_: set_webgui_visible(False))

        # webgui_selector = Group(id="webgui_selector", components=[geo_button, mesh_button], horizontal=True)

        # def download_mesh(btn):
        #     if self.mesh is not None:
        #         self.mesh.Save("mesh.vol")
        #         btn.callJSFunction("download", { "filename" : "mesh.vol" })
        # self.download_mesh_button.on("click", download_mesh)

        # def generate_mesh(btn):
        #     meshing_pars = {}
        #     with Loading(self.component):
        #         shape = self.geo.shape
        #         import netgen.occ as ngocc
        #         for solid, s in zip(self.solids.shape_components, shape.solids):
        #             if solid.nameParam.value:
        #                 s.name = solid.nameParam.value
        #             if solid.maxh.value:
        #                 s.maxh = solid.maxh.value
        #         for face, f in zip(self.faces.shape_components, shape.faces):
        #             if face.nameParam.value:
        #                 f.name = face.nameParam.value
        #             if face.maxh.value:
        #                 f.maxh = face.maxh.value
        #         for edge, e in zip(self.edges.shape_components, shape.edges):
        #             if edge.nameParam.value:
        #                 e.name = edge.nameParam.value
        #             if edge.maxh.value:
        #                 e.maxh = edge.maxh.value
        #         geo = ngocc.OCCGeometry(self.original_geo.shape)
        #         if self.meshsize.value is not None:
        #             meshing_pars["maxh"] = float(self.meshsize.value)
        #         self.mesh = geo.GenerateMesh(**meshing_pars)
        #         self.webgui.dynamic.visible=False
        #         self.webgui2.dynamic.visible=True
        #         updateFrontendComponents([self.webgui, self.webgui2])
        #         self.download_mesh_button.dynamic.disabled = False
        #         self.download_mesh_button.updateFrontend()
        #         self.webgui2.draw(self.mesh)

        # self.generate_mesh_button.on("click", generate_mesh)

        # webgui_group = Group(id="webgui_group",
        #                      components=[webgui_selector, self.webgui, self.webgui2])
        # horiz_group = Group(id="horiz_group",
        #                     components=[self.shape_selector,
        #                                 webgui_group],
        #                     horizontal=True)
        # self.component = Group(id="main",
        #                        components=[upload_group,
        #                                    horiz_group,
        #                                    global_parameters])

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
                self.edges.on_shape_select()
            elif args["dim"] == 2:
                face = self.faces.shapes[args["index"]]
                print("args = ", args)
        else:
             if args["dim"] == 2:
                one = False
                for solid in self.face_neighbours[self.faces.shapes[args["index"]]]:
                    if self.solids[self.solid_indices[solid]].visibleParam.value:
                        one = not one
                if one:
                    index = self.solid_indices[solid]
                    self.solids.selector.input.value = index
                    self.solids.selector.updateFrontend()
                    self.solids[index].selected = \
                        not self.solids[index].selected
        self.redraw()

    def draw(self):
        self.webgui.draw(self.geo.shape)

    def redraw(self):
        # Here we actually just need to reset the face and edge colors
        self.draw()

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"

    def run(self, result_dir):
        pass

    def _update_geometry(self):
        print("call update geometry")
        with self.geo_upload as geofile:
            import netgen.occ as ngocc
            self.geo = ngocc.OCCGeometry(geofile).shape
            print("still in geofile")
        print("self.geo = ", self.geo)
        face_components = []
        for i, face in enumerate(self.geo.faces):
            print("add face", i, face)
            comp = ShapeComponent("face_" + str(i+1), face)
            face_components.append(comp)
        print("face children = ", face_components)
        self.faces.children = face_components
        self.faces.update_frontend()
        print("set dialogs")
        self.geo_upload_dialog.hidden = True
        self.main_dialog.hidden = False
        self.geo_upload_dialog.update_frontend()
        self.main_dialog.update_frontend()

    def restart(self):
        self.geo = None
        self.main_dialog.hidden = True
        self.main_dialog.update_frontend()
        self.geo_upload.model_value = None
        self.geo_upload.update_frontend()
        self.geo_upload_dialog.hidden = False
        self.geo_upload_dialog.update_frontend()

    def create_geo_upload_layout(self):
        self.geo_upload = FileUpload(self,
                                     id="geo_file",
                                    label="Upload geometry",
                                    accept="step,stp,brep",
                                    error_title="Error in Geometry Upload",
                                    error_text="Please upload a valid geometry file")
        self.geo_upload.on_file_loaded_callbacks.append(self._update_geometry)
        welcome_header = Div(classes="text-h6",
                           children="Welcome to the Meshing App!",
                           style="padding-top:100px;text-align:center;")
        welcome_text = Div(style="text-align:center;",
                           children="Upload a geometry file to get started. Currently supported geometry formats: step (*.step, *.stp), brep (*.brep)")

        # This is not really nice...
        self.geo_upload_dialog = QCard(
            flat=True,
            classes="q-ma-lg q-pa-lg q-center gt-sm",
            children=[welcome_header, welcome_text, Div(
                Col(self.geo_upload),
                classes="column items-center")])
    
    def create_layout(self):
        self.create_geo_upload_layout()
        self.create_main_layout()
        self.component = Div([self.geo_upload_dialog, self.main_dialog])

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        if self.geo_upload.filename is not None:
            self._update_geometry()

    def create_main_layout(self):
        self.shapetype_selector = QBtnToggle(model_value="Faces",
                                             options=["Solids", "Faces", "Edges"])


        sim_name = QInput(model_value=self.name,
                          id="simulation_name",
                          label="Simulation Name",
                          debounce=200,
                          style="padding-left:10px;",
                          clearable=True)
        save_button = QBtn(flat=True, icon="save",
                           children=QTooltip(children="Save simulation",
                                             style="min-width:400px;"))
        save_button.on_click(self.save)
        gen_mesh_btn = QBtn(icon="mdi-arrow-right-drop-circle-outline",
                            flat=True,
                            children=QTooltip(children="Generate Mesh"))
        download_mesh_btn = QBtn(icon="download",
                                 flat=True,
                                 children=QTooltip(children="Download Mesh"))
        restart_btn = QBtn(icon="mdi-restart",
                           flat=True,
                           children=QTooltip(children="Go back to upload geometry"))
        restart_btn.on_click(self.restart)
        footer = QFooter(classes="row text-black bg-grey-3",
                         children=[sim_name, QSpace(), restart_btn, save_button,
                                   gen_mesh_btn, download_mesh_btn])

        self.faces = QList()
        inner = Div(self.faces)

        big_device = QCard(flat=True, classes="q-ma-lg q-pa-lg q-center gt-sm",
                           children=inner,
                           bordered=True)
        small_device = QCard(flat=True, classes="lt-md", children=inner)
        self.main_dialog = Div([small_device, big_device, footer])
        self.main_dialog.hidden = True
