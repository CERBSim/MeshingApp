from webapp_client.app import App, register_application
from webapp_client.components import Row, Col, Div, FileUpload, Heading, Centered
from webapp_client.qcomponents import *
from webapp_client.visualization import WebguiComponent
from .version import __version__

class FileDownload(QBtn):
    def __init__(self, id, *args, **kwargs):
        """A button that downloads a file on click.

        The file can be set with set_file(filename, file_data=None, file_location=None).

        The file data is stored in the storage of the app and only retrieved when the button is clicked.
        """
        super().__init__(id=id, *args, **kwargs)
        self._filename = None
        self.disable = True
        self.on("click",self.download)

    def set_file(self, filename, file_data=None, file_location=None):
        """Set the file to be downloaded on button click as file with name filename.

        If file_data is set, it is used as file content, otherwise the file is read from file_location. If no file location is given as well, the file is read from the current directory with the given filename.
        """
        assert file_data is None or file_location is None, "Only file data or file location can be set"
        self._filename = filename
        if file_data is not None:
            self.storage.set("file", file_data)
        else:
            if file_location is None:
                file_location = filename
            with open(file_location, "rb") as f:
                file_data = f.read()
                self.storage.set("file", file_data)
        self.disable = False

    def download(self):
        if self._filename is not None:
            result = self.storage.get("file")
            self.download_file(data=result, filename=self._filename)

    def dump(self):
        return self._filename

    def load(self, data):
        self._filename = data
        self.disable = self._filename == None

class MainLayout(Div):
    def __init__(self, *args):
        super().__init__(*args, id="main")
        self.shape = None
        self.hidden = True
        self.webgui = WebguiComponent(id="webgui_geo")
        self.mesh_webgui = WebguiComponent(id="webgui_mesh")
        self.mesh_webgui.hidden = True
        def update_gui():
            print("update gui, value = ", self.gui_toggle.model_value)
            self.webgui.hidden = self.gui_toggle.model_value != "geo"
            self.mesh_webgui.hidden = self.gui_toggle.model_value != "mesh"
        self.gui_toggle = QBtnToggle(push=True,
            model_value="geo", options=[{ "label" : "Geometry",
                                               "value" : "geo" },
                                             { "label" : "Mesh",
                                               "value" : "mesh" }], style="margin-top:40px;",
        ).on_update_model_value(update_gui)
        
        def click_webgui(args):
            if self.shapetype_selector.model_value == "faces":
                dim = args["value"]["dim"]
                if dim == 2:
                    index = args["value"]["index"]
                    print("index = ", index)
            print("click_webgui = ", args)
        self.webgui.on_click(click_webgui)
        webgui_card = QCard(style="margin:20px;",
                            children=[Centered(self.gui_toggle), self.webgui, self.mesh_webgui])
        self.shapetype_selector = QBtnToggle(push=True,
            model_value="faces", options=[{ "label" : "Solids",
                                           "value" : "solids" },
                                          { "label" : "Faces",
                                            "value" : "faces" },
                                          { "label" : "Edges",
                                            "value" : "edges" }],
            style="margin-bottom:10px;")
        self.shapetype_selector.on_update_model_value(self.update_table_visiblity)
        columns = [{ "name" : "index", "label" : "Index", "field": "index" },
                   { "name" : "name", "label" : "Name", "field": "name" },
                   { "name" : "maxh", "label" : "Maxh", "field": "maxh" },
                   { "name" : "visible", "label" : "Visible", "field": "visible" }]
        self.solid_table = QTable(
                                  row_key="index",
                                  flat=True,
                                  columns=columns,
                                  style="min-width: 450px;",
                                  )
        self.solid_table.hidden = True
        self.face_table = QTable(row_key="index",
                                 flat=True,
                                 columns=columns,
                                 selection="multiple",
                                 style="min-width: 450px;",
                                 )
        self.edge_table = QTable(row_key="index",
                                 flat=True,
                                 columns=columns,
                                 style="min-width: 450px;",
                                 )
        self.edge_table.hidden = True
        settings = QCard(style="margin:20px;padding:20px;",
                         children=[
                             QCardSection(
                                 children=[
                                     Centered(self.shapetype_selector),
                                     self.solid_table,
                                     self.face_table,
                                     self.edge_table])])

        generate_mesh_button = QBtn(fab=True,
                                    icon="mdi-arrow-right-drop-circle-outline",
                                    color="primary",
                                    children=QTooltip(children="Generate Mesh"),
                                    style="position: absolute; right: 140px; bottom: 20px;").on_click(self.generate_mesh)

        self.download_mesh_button = FileDownload(
            id="download_mesh",
            fab=True,
            icon="download",
            color="primary",
            disable=True,
            children=QTooltip(children="Download Mesh"),
            style="position: absolute; right: 80px; bottom: 20px;")
        self.children = [Centered(Row(settings, webgui_card)),
                         generate_mesh_button, self.download_mesh_button]

    def generate_mesh(self):
        import netgen.occ as ngocc
        # ngocc.ResetGlobalShapeProperties()
        geo = ngocc.OCCGeometry(self.shape)
        mesh = geo.GenerateMesh()
        mesh.Save(self.name + ".vol.gz")
        self.download_mesh_button.set_file(self.name + ".vol.gz")
        self.mesh_webgui.draw(mesh)
        self.gui_toggle.model_value = "mesh"
        self.mesh_webgui.hidden = False
        self.webgui.hidden = True

    def update_table_visiblity(self):
        self.solid_table.hidden = self.shapetype_selector.model_value != "solids"
        self.face_table.hidden = self.shapetype_selector.model_value != "faces"
        self.edge_table.hidden = self.shapetype_selector.model_value != "edges"

    def build_from_shape(self, shape, name):
        self.shape = shape
        self.name = name
        self.shape.faces.col = (0.7, 0.7, 0.7)
        self.webgui.draw(self.shape)
        solid_rows = []
        for i, solid in enumerate(self.shape.solids):
            solid_rows.append( { "index" : i,
                                 "name" : solid.name,
                                 "maxh" : None if solid.maxh > 1e98 else solid.maxh,
                                 "visible" : True })
        self.solid_table.rows = solid_rows
        face_rows = []
        for i, face in enumerate(self.shape.faces):
            face_rows.append( { "index" : i,
                                "name" : face.name,
                                "maxh" : None if face.maxh > 1e98 else face.maxh,
                                "visible" : True })
        self.face_table.rows = face_rows
        edge_rows = []
        for i, edge in enumerate(self.shape.edges):
            edge_rows.append( { "index" : i,
                                "name" : edge.name,
                                "maxh" : None if edge.maxh > 1e98 else edge.maxh,
                                "visible" : True })
        self.edge_table.rows = edge_rows
        self.hidden = False

@register_application
class MeshingModel(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo = None
        self.create_layout()

    def create_layout(self):
        self.geo_upload_layout = self.create_geo_upload_layout()
        self.main_layout = MainLayout()
        save_button = QBtn(
            fab=True,
            icon="save",
            color="primary",
            children=QTooltip(children="Save"),
            style="position: absolute; right: 20px; bottom: 20px;",
        ).on_click(self.save)
        self.main_layout.children.append(save_button)
        self.component = Div(self.geo_upload_layout, self.main_layout)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        if self.geo_upload.filename is not None:
            self._update_geometry()

    def _update_geometry(self):
        import os
        self.name = os.path.splitext(self.geo_upload.filename)[-2]
        print("Set name to ", self.name)
        with self.geo_upload as geofile:
            import netgen.occ as ngocc
            self.main_layout.build_from_shape(shape=ngocc.OCCGeometry(geofile).shape,
                                              name=self.name)
        self.geo_upload_layout.hidden = True

    def restart(self):
        self.geo_upload.model_value = None
        self.geo_upload_layout.hidden = False
        self.main_layout.hidden = True
        self.main_layout.shape = None

    def create_geo_upload_layout(self):
        self.geo_upload = FileUpload(
            self,
            id="geo_file",
            label="Upload geometry",
            accept="step,stp,brep",
            error_title="Error in Geometry Upload",
            error_message="Please upload a valid geometry file",
        )
        self.geo_upload.on_file_loaded(self._update_geometry)
        welcome_header = Heading(
            "Welcome to the Meshing App!",
            6,
            style="text-align:center;"
        )
        welcome_text = Div(
            "Upload a geometry file to get started. Currently supported geometry formats: step (*.step, *.stp), brep (*.brep)",
            style="text-align:center;",
        )

        return Div(welcome_header,
                   welcome_text,
                   Centered(self.geo_upload), classes="fixed-center")
    
    def create_main_layout(self):
        self.shapetype_selector = QBtnToggle(
            model_value="Faces", options=["Solids", "Faces", "Edges"]
        )

        sim_name = QInput(
            model_value=self.name,
            id="simulation_name",
            label="Simulation Name",
            debounce=200,
            style="padding-left:10px;",
            clearable=True,
        )
        save_button = QBtn(
            flat=True,
            icon="save",
            children=QTooltip(children="Save simulation", style="min-width:400px;"),
        )
        save_button.on_click(self.save)
        gen_mesh_btn = QBtn(
            icon="mdi-arrow-right-drop-circle-outline",
            flat=True,
            children=QTooltip(children="Generate Mesh"),
        )
        gen_mesh_btn.on_click(self.run)
        self.download_mesh_btn = FileDownload(id="download_mesh",
            icon="download", flat=True, children=QTooltip(children="Download Mesh")
        )
        restart_btn = QBtn(
            icon="mdi-restart",
            flat=True,
            children=QTooltip(children="Go back to upload geometry"),
        )
        restart_btn.on_click(self.restart)
        footer = QFooter(
            classes="row text-black bg-grey-3",
            children=[
                sim_name,
                QSpace(),
                restart_btn,
                save_button,
                gen_mesh_btn,
                download_mesh_btn,
            ],
        )

        self.faces = QList()
        inner = Div(self.faces)

        big_device = QCard(
            flat=True,
            classes="q-ma-lg q-pa-lg q-center gt-sm",
            children=inner,
            bordered=True,
        )
        small_device = QCard(flat=True, classes="lt-md", children=inner)
        return MainLayout("HI") #small_device, big_device, footer)

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
                self.faces[args["index"]].selected = not self.faces[
                    args["index"]
                ].selected
                self.faces.on_shape_select()
        elif self.shapetype_selector.input.value == "Edges":
            if args["dim"] == 1:
                self.edges.selector.input.value = args["index"]
                self.edges.selector.updateFrontend()
                self.edges[args["index"]].selected = not self.edges[
                    args["index"]
                ].selected
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
                    self.solids[index].selected = not self.solids[index].selected
        self.redraw()

    def draw(self):
        self.webgui.draw(self.geo.shape)

    def redraw(self):
        # Here we actually just need to reset the face and edge colors
        self.draw()

    def run(self):
        pass

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


class ShapeComponent(QItem):
    def __init__(self, id, shape):
        self.nameParam = QInput(
            id=id + "_name",
            label="Name",
            model_value=shape.name,
            debounce=200,
            style="min-width: 200px",
        ).on_update_model_value(self.set_name)
        self.maxh = QInput(
            id=id + "_maxh",
            label="Meshsize",
            type="number",
            debounce=200,
            model_value=shape.maxh if shape.maxh < 1e98 else None,
        ).on_update_model_value(self.set_maxh)
        super().__init__(
            children=Row(
                *[QItemSection(children=c) for c in [self.nameParam, self.maxh]]
            )
        )
        self._shape = shape

    def set_name(self, name):
        self._shape.name = name

    def set_maxh(self, maxh):
        self._shape.maxh = maxh

# class ShapeGroup(DynamicGroup):
#     def __init__(
#         self,
#         id,
#         *args,
#         redraw_command=None,
#         default_color=(0.7, 0.7, 0.7),
#         highlight_color=(1, 0, 0),
#         **kwargs
#     ):
#         self.selector = SelectionDialog(
#             id=id + "_sel_group",
#             labels=[],
#             values=[],
#             variant="dropdown",
#         )
#         self.selector.dynamic.label = "Select " + kwargs["name"]
#         self.selector.dynamic.style = "width: 400px"
#         self.selector.on("update", self.on_shape_select)
#         self._redraw_command = redraw_command
#         self._default_color = default_color
#         self._highlight_color = highlight_color
#         self._shapes = []
#         components = [self.selector]
#         super().__init__(id=id, *args, components=components, inline=True, **kwargs)

#     @property
#     def shape_components(self):
#         return self.components[1:]

#     def on_shape_select(self):
#         print("on_shape_select, ", self.selector.value)
#         selected = self.selector.input.value
#         for i, shape in enumerate(self.shape_components):
#             shape.selected = i == selected
#             shape.dynamic.visible = i == selected
#         updateFrontendComponents(self.components)
#         self._redraw_command()

#     def __getitem__(self, index):
#         return self.shape_components[index]

#     @property
#     def shapes(self):
#         return self._shapes

#     @shapes.setter
#     def shapes(self, shapes):
#         self._shapes = shapes
#         shape_components = []
#         labels = []
#         values = []
#         for i, shape in enumerate(shapes):
#             labels.append(
#                 self.name[:-1]
#                 + " "
#                 + str(i)
#                 + ("" if not shape.name else " (" + shape.name + ")")
#             )
#             values.append(i)
#             shape_components.append(
#                 ShapeComponent(
#                     id=self._id + "_" + str(i),
#                     shape=shape,
#                     redraw_command=self._redraw_command,
#                     default_color=self._default_color,
#                     highlight_color=self._highlight_color,
#                 )
#             )
#             shape_components[-1].dynamic.visible = False
#         self.replace_components([self.selector] + shape_components)
#         self.selector.dynamic.labels = labels
#         self.selector.dynamic.values = values
#         self.selector.updateFrontend()

