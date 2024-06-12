from webapp_client.app import App, register_application, current_model
from webapp_client.components import *
from webapp_client.qcomponents import *
from webapp_client.utils import temp_dir_with_files
from webapp_client.visualization import WebguiComponent
from .version import __version__
import webapp_client.api as api
import datetime

mesh_options = {
    "very_coarse": {"curvaturesafety": 1, "segmentsperedge": 0.3, "grading": 0.7},
    "coarse": {"curvaturesafety": 1.5, "segmentsperedge": 0.5, "grading": 0.5},
    "moderate": {"curvaturesafety": 2, "segmentsperedge": 1, "grading": 0.3},
    "fine": {"curvaturesafety": 3, "segmentsperedge": 2, "grading": 0.3},
    "very_fine": {"curvaturesafety": 5, "segmentsperedge": 3, "grading": 0.1},
}


class SimulationTable(QTable):
    def __init__(self, dialog):
        super().__init__(
            title="Load Geometry",
            pagination={"rowsPerPage": 5},
            columns=[
                {"name": "index", "label": "Index", "field": "index"},
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "name", "label": "Name", "field": "name"},
                {"name": "created", "label": "Created", "field": "created"},
                {"name": "modified", "label": "Modified", "field": "modified"},
            ],
            visible_columns=["name", "created", "modified"],
            style="padding:20px;min-width:700px;",
        )
        self.slot_header = [
            QTr(
                QTh("Name"),
                QTh("Created"),
                QTh("Modified"),
                QTh("Actions"),
                style="position:sticky;top:0;z-index:1;background-color:white;",
            )
        ]
        self.slot_body = self.create_row
        self.dialog = dialog

    def load_simulation(self, event):
        self.dialog.hide()
        self.dialog.app.loading.hidden = False
        file_id = event["arg"]["file_id"]
        res = api.get(f"/model/{file_id}")
        import webapp_frontend

        webapp_frontend.set_file_id(file_id)
        self.dialog.app.load(data=res["data"], metadata=res["metadata"])
        self.dialog.app.loading.hidden = True

    def delete_simulation(self, event):
        file_id = event["arg"]["file_id"]
        api.delete(f"/files/{file_id}")
        # TODO: can we somehow prevent propagation of on click here to row?
        self.rows = [r for r in self.rows if r["id"] != file_id]

    def create_row(self, props):
        row = props["row"]
        created = datetime.datetime.fromtimestamp(row["created"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        modified = datetime.datetime.fromtimestamp(row["modified"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        delete_btn = QBtn(icon="delete", color="negative", flat=True)
        delete_btn.on_click(self.delete_simulation, arg={"file_id": row["id"]})
        # TODO: If we can prevent onclick propagation on delete btn we can
        # set this on click on the whole row.
        name, create, modified = QTd(row["name"]), QTd(created), QTd(modified)
        for c in [name, create, modified]:
            c.on("click", self.load_simulation, arg={"file_id": row["id"]})
        row_comp = QTr(name, create, modified, QTd(delete_btn))
        return [row_comp]


class LoadDialog(QDialog):
    def __init__(self, *args, app, **kwargs):
        self.app = app
        self.simulations = SimulationTable(dialog=self)
        card = self.simulations
        super().__init__(card, *args, **kwargs)

    def show(self):
        super().show()
        res = api.get("/simulations")
        sims = [
            s
            for s in res
            if s["app_id"] == self.app.metadata["app_id"] and not s["deleted"]
        ]
        for i, s in enumerate(sims):
            s["index"] = i
        self.simulations.rows = sims

class GlobalMeshingSettings(QCard):
    def __init__(self):
        def change_mesh_granularity():
            mp = mesh_options[self.mesh_granularity.model_value]
            self.curvature_safety.model_value = mp["curvaturesafety"]
            self.segments_per_edge.model_value = mp["segmentsperedge"]
            self.grading.model_value = mp["grading"]

        self.mesh_granularity = QSelect(
            QTooltip(
                Div(
                    "Predefined meshing settings. Selection changes global settings.",
                    style="max-width:300px;",
                )
            ),
            id="mesh_granularity",
            model_value="moderate",
            options=list(mesh_options.keys()),
            style="padding-left:30px;min-width:200px;",
        ).on_update_model_value(change_mesh_granularity)

        self.maxh = QInput(
            QTooltip(
                Div(
                    "Maximum mesh size. Not strictly enforced (if mesh quality would suffer too much).",
                    style="max-width:300px;",
                )
            ),
            id="maxh",
            label="Maxh",
            type="number",
        )
        self.curvature_safety = NumberInput(
            QTooltip(
                Div(
                    "Factor reducing mesh size depending on curvature radius of the face, meshsize is approximately curvature radius divided by this factor.",
                    style="max-width:300px;",
                )
            ),
            model_value=2.0,
            id="curvature_safety",
            label="Curvature Safety",
        )
        self.segments_per_edge = NumberInput(
            QTooltip(
                Div(
                    "Reduces mesh size, such that each edge is divided at least into this number of segments. Setting to factor less than one sets meshsize to 1/factor * edge length. Leave empty to disable.",
                    style="max-width:300px;",
                )
            ),
            id="segments_per_edge",
            clearable=True,
            label="Segments per Edge",
        )
        self.grading = QSlider(
            model_value=0.3,
            min=0.01,
            max=0.99,
            step=0.01,
            id="grading",
            label=True,
        )

        super().__init__(
            Heading("Global Meshing Settings", 3),
            self.mesh_granularity,
            self.maxh, self.curvature_safety,
                self.segments_per_edge,
                Div(
                    "Grading",
                    QTooltip(
                        Div(
                            "Factor controlling how quickly elements can become coarser close to refined regions. Between 0 and 1, 1 means no grading, 0 means maximum grading.",
                            style="width:300px;",
                        )
                    ),
                    self.grading,
                    classes="q-field__label",
                    style="margin-top:10px;width:200px;",
                ),
            id="global_settings",
            style="margin:10px;padding:30px;",
            namespace=True,
        )

    def get_meshing_parameters(self):
        mp = {}
        if self.maxh.model_value:
            mp["maxh"] = float(self.maxh.model_value)
        if self.curvature_safety.model_value:
            mp["curvaturesafety"] = float(self.curvature_safety.model_value)
        if self.segments_per_edge.model_value:
            mp["segmentsperedge"] = float(self.segments_per_edge.model_value)
        if self.grading.model_value:
            mp["grading"] = float(self.grading.model_value)
        return mp


class ShapeTable(QTable):
    def __init__(self, geo_webgui, shape_type):
        columns = [
            {"name": "index", "label": "Index", "field": "index"},
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "maxh", "label": "Maxh", "field": "maxh"},
            {"name": "visible", "label": "Visible", "field": "visible"},
        ]
        super().__init__(
            id=shape_type,
            row_key="index",
            flat=True,
            columns=columns,
            style="min-width: 450px;height:650px;",
            title="Shape Settings",
            pagination={"rowsPerPage": 6 },
            selection="multiple",
        )
        self.shapes = []
        self.selected = []
        self.row_components = {}
        self.slot_body = self.create_row
        self.slot_header = [
            QTr(
                QTh("Index"),
                QTh("Name"),
                QTh("Maxh"),
                QTh("Visible"),
                style="position:sticky;top:0;z-index:1;background-color:white;",
            )
        ]
        self.search_input = QInput(
            name="Search", dense=True, debounce=500
        ).on_update_model_value(self.search)
        self.search_input.slot_append = [QIcon(name="search")]
        self.slot_top_right = [
            self.search_input,
            QBtn("Select All", flat=True).on_click(self.select_all),
        ]
        self.last_clicked = None
        self.geo_webgui = geo_webgui
        self.shape_type = shape_type
        self._loaded_rows = []
        self.select_row_callback = []
        self.name_inputs = {}
        self.maxh_inputs = {}
        self.visible_cbs = {}
        self.faces = {}
        self.edges = {}

    def search(self, event):
        if event["value"] == "":
            self.rows = self.all_rows

        else:
            self.rows = [
                row
                for row in self.all_rows
                if (
                    row["name"] is not None
                    and event["value"].lower() in row["name"].lower()
                )
            ]

    def select_all(self):
        self.selected = list(range(len(self.rows)))
        self.color_rows()

    def click_row(self, event):
        row_index = event["arg"]["row"]
        if "ctrlKey" in event and event["ctrlKey"]:
            sel = self.selected
            if row_index in self.selected:
                sel.remove(row_index)
            else:
                sel.append(row_index)
            self.selected = sel
        elif "shiftKey" in event and event["shiftKey"]:
            if self.last_clicked is not None:
                start = min(row_index, self.last_clicked)
                end = max(row_index, self.last_clicked)
                self.selected = list(range(start, end + 1))
            else:
                self.selected = [row_index]
        else:
            self.selected = [row_index]
        self.last_clicked = row_index
        self.color_rows()
        for cb in self.select_row_callback:
            cb()

    def color_rows(self):
        self.hide_bottom = len(self.selected) == 0
        for index, row in self.row_components.items():
            if index in self.selected:
                row.style = "background-color: #f0f0f0;"
            else:
                row.style = ""
        self.update_gui()

    def update_gui(self):
        if self.shape_type == "solids":
            self.geo_webgui._webgui_data["edge_colors"] = [
                (0, 0, 0, v[3] if len(v) == 4 else 1)
                for v in self.geo_webgui._webgui_data["edge_colors"]
            ]
            drawn_faces = set()
            self.geo_webgui._webgui_data["colors"] = [
                (0.7, 0.7, 0.7, 1) for _ in self.geo_webgui._webgui_data["colors"]
            ]
            for index, shape in enumerate(self.shapes):
                if self.rows[index]["visible"]:
                    for face in shape.faces:
                        drawn_faces.add(self.face_index[face])
                if index in self.selected:
                    for face in shape.faces:
                        self.geo_webgui._webgui_data["colors"][
                            self.face_index[face]
                        ] = (1, 0, 0, 1)
            for index in range(len(self.geo_webgui._webgui_data["colors"])):
                if index not in drawn_faces:
                    self.geo_webgui._webgui_data["colors"][index] = (1, 1, 1, 0)
        elif self.shape_type == "faces":
            self.geo_webgui._webgui_data["edge_colors"] = [
                (0, 0, 0, v[3] if len(v) == 4 else 1)
                for v in self.geo_webgui._webgui_data["edge_colors"]
            ]
            for index, shape in enumerate(self.shapes):
                if not self.rows[index]["visible"]:
                    self.geo_webgui._webgui_data["colors"][index] = (1, 1, 1, 0)
                    continue
                if index in self.selected:
                    self.geo_webgui._webgui_data["colors"][index] = (1, 0, 0, 1)
                else:
                    self.geo_webgui._webgui_data["colors"][index] = (0.7, 0.7, 0.7, 1)
        else:
            self.geo_webgui._webgui_data["colors"] = [
                (0.7, 0.7, 0.7, v[3]) for v in self.geo_webgui._webgui_data["colors"]
            ]
            for index, shape in enumerate(self.shapes):
                if not self.rows[index]["visible"]:
                    self.geo_webgui._webgui_data["edge_colors"][index] = (1, 1, 1, 0)
                    continue
                if index in self.selected:
                    self.geo_webgui._webgui_data["edge_colors"][index] = (1, 0, 0, 1)
                else:
                    self.geo_webgui._webgui_data["edge_colors"][index] = (0, 0, 0, 1)

        if self.faces == {}:
            self.faces = {
                i: color
                for i, color in enumerate(self.geo_webgui._webgui_data["colors"])
            }
        if self.edges == {}:
            self.edges = {
                i: color
                for i, color in enumerate(self.geo_webgui._webgui_data["edge_colors"])
            }

        faces = {
            i: (0.7, 0.7, 0.7, 1)
            for i in range(len(self.geo_webgui._webgui_data["colors"]))
        }
        edges = {
            i: (0, 0, 0, 1)
            for i in range(len(self.geo_webgui._webgui_data["edge_colors"]))
        }
        faces.update(self.faces)
        edges.update(self.edges)

        def diff_dicts(dict1, webgui_data, type="faces"):
            target_value = (0.7, 0.7, 0.7, 1) if type == "faces" else (0, 0, 0, 1)
            dict2 = {i: data for i, data in enumerate(webgui_data)}
            return {
                key: value
                for key, value in dict2.items()
                if dict1[key] != value or dict1[key] != target_value
            }

        if diff := diff_dicts(faces, self.geo_webgui._webgui_data["colors"], "faces"):
            self.faces = diff
        if diff := diff_dicts(
            edges, self.geo_webgui._webgui_data["edge_colors"], "edges"
        ):
            self.edges = diff
        self.geo_webgui.set_color(faces=self.faces, edges=self.edges)

    def dump(self):
        return {"base": super().dump(), "rows": self.rows}

    def load(self, data):
        if "base" in data and data["base"] is not None:
            super().load(data["base"])
        if "rows" in data:
            self._loaded_rows = data["rows"]

    def set_name(self, data):
        self.shapes[data["arg"]["row"]].name = data["value"]
        self.rows[data["arg"]["row"]]["name"] = data["value"]
        if "update_inputs" in data and data["update_inputs"]:
            self.name_inputs[data["arg"]["row"]].model_value = data["value"]

    def set_maxh(self, data):
        maxh = (
            1e99
            if (data["value"] is None or data["value"] == "")
            else float(data["value"])
        )
        self.shapes[data["arg"]["row"]].maxh = maxh
        self.rows[data["arg"]["row"]]["maxh"] = maxh
        if "update_inputs" in data and data["update_inputs"]:
            self.maxh_inputs[data["arg"]["row"]].model_value = data["value"]

    def set_visible(self, data):
        self.rows[data["arg"]["row"]]["visible"] = data["value"]
        if "update_inputs" in data and data["update_inputs"]:
            self.visible_cbs[data["arg"]["row"]].model_value = data["value"]
        self.update_gui()

    def create_row(self, props):
        row = props["row"]

        visible_cb = QCheckbox(model_value=row["visible"]).on_update_model_value(
            self.set_visible, arg={"row": row["index"]}
        )
        name_input = QInput(
            label="Name", debounce=500, model_value=row.get("name", None)
        ).on_update_model_value(self.set_name, arg={"row": row["index"]})
        maxh_val = row.get("maxh", None)
        if maxh_val is not None and maxh_val > 1e98:
            maxh_val = None
        maxh_input = NumberInput(
            label="Maxh",
            model_value=maxh_val,
        ).on_update_model_value(self.set_maxh, arg={"row": row["index"]})
        self.name_inputs[row["index"]] = name_input
        self.maxh_inputs[row["index"]] = maxh_input
        self.visible_cbs[row["index"]] = visible_cb
        row_comp = QTr(
            QTd(str(row["index"])),
            QTd(name_input),
            QTd(maxh_input),
            QTd(visible_cb),
        ).on("click", self.click_row, arg={"row": row["index"]})
        self.row_components[row["index"]] = row_comp
        return [row_comp]

    def set_shapes(self, shapes, face_index=None):
        self.shapes = shapes
        self.face_index = face_index
        rows = []
        for i, shape in enumerate(shapes):
            rows.append(
                {
                    "index": i,
                    "name": shape.name if shape.name else None,
                    "maxh": None if shape.maxh > 1e98 else shape.maxh,
                    "visible": True,
                }
            )
        self.rows = rows
        self.all_rows = rows
        if self._loaded_rows:
            for i, r in enumerate(self._loaded_rows):
                # use the callback structure
                self.set_name({"value": r["name"], "arg": {"row": i}})
                self.set_maxh({"value": r["maxh"], "arg": {"row": i}})


class MainLayout(Div):
    def __init__(self, *args):
        self.alert_dialog = QDialog(Heading("Error"), "")
        super().__init__(self.alert_dialog, *args, id="main")
        self.shape = None
        self.hidden = True
        # Webgui needs to be wrapped in div so that hide/show works properly?
        self.webgui = WebguiComponent(id="webgui_geo")
        self.webgui.style = "min-width:500px;height:700px"
        self.webgui_div = Div(self.webgui)
        self.mesh_webgui = WebguiComponent(id="webgui_mesh")
        self.mesh_webgui.style = "min-width:500px;height:700px"
        self.mesh_webgui_div = Div(self.mesh_webgui)
        self.mesh_webgui_div.hidden = True

        def update_gui():
            def mesh_to_geo(args):
                camera_settings = self.mesh_webgui._settings["camera"]
                self.webgui.set_camera(camera_settings)

            def geo_to_mesh(args):
                camera_settings = self.webgui._settings["camera"]
                self.mesh_webgui.set_camera(camera_settings)

            if self.gui_toggle.model_value == "geo":
                self.mesh_webgui.update_camera_settings(mesh_to_geo)
            else:
                self.webgui.update_camera_settings(geo_to_mesh)
            self.webgui_div.hidden = self.gui_toggle.model_value != "geo"
            self.mesh_webgui_div.hidden = self.gui_toggle.model_value != "mesh"

        self.gui_toggle = QBtnToggle(
            push=True,
            model_value="geo",
            options=[
                {"label": "Geometry", "value": "geo"},
                {"label": "Mesh", "value": "mesh"},
            ],
            style="margin-top:40px;",
        ).on_update_model_value(update_gui)

        def click_webgui(args):
            dim = args["value"]["dim"]
            if args["value"]["did_move"]:
                return
            if dim == -1:
                table = self.shapetype_tables[self.shapetype_selector.model_value]
                table.selected = []
                table.color_rows()
                return
                # table.update_selected(table.selected)
            if dim == 2:
                index = args["value"]["index"]
                self.shapetype_selector.model_value = "faces"
                self.update_table_visiblity()
                # TODO: Find a good way to go to the correct page
                self.face_table.firstPage()
                for _ in range(index//self.face_table.pagination["rowsPerPage"]):
                    self.face_table.nextPage()
                self.face_table.click_row(args["value"] | {"arg": {"row": index}})
            if dim == 1:
                index = args["value"]["index"]
                self.shapetype_selector.model_value = "edges"
                self.update_table_visiblity()
                # TODO: Find a good way to go to the correct page
                self.edge_table.firstPage()
                for _ in range(index//self.edge_table.pagination["rowsPerPage"]):
                    self.edge_table.nextPage()
                self.edge_table.click_row(args["value"] | {"arg": {"row": index}})

        self.webgui.on_click(click_webgui)
        self.geo_info = Div(style="padding-left:5px;")
        webgui_card = QCard(
            Centered(self.gui_toggle),
            self.webgui_div,
            self.mesh_webgui_div,
            self.geo_info,
            style="margin:10px; fit;width:800px;height:800px;",
        )
        self.shapetype_selector = QBtnToggle(
            push=True,
            model_value="faces",
            options=[
                {"label": "Solids", "value": "solids"},
                {"label": "Faces", "value": "faces"},
                {"label": "Edges", "value": "edges"},
            ],
            style="margin-bottom:10px;",
        )
        self.shapetype_selector.on_update_model_value(self.update_table_visiblity)
        self.solid_table = ShapeTable(self.webgui, "solids")
        self.solid_table.hidden = True
        self.face_table = ShapeTable(self.webgui, "faces")

        def create_body_cell(props):
            return [QTd(QInput(label=props["col"]["label"]))]

        self.face_table.slot_body_cell_name("name", create_body_cell)

        self.edge_table = ShapeTable(self.webgui, "edges")
        self.edge_table.hidden = True
        self.shapetype_tables = {
            "solids": self.solid_table,
            "faces": self.face_table,
            "edges": self.edge_table,
        }

        def set_selected_name():
            name = self.change_name.model_value
            table = self.shapetype_tables[self.shapetype_selector.model_value]
            for index in table.selected:
                table.set_name(
                    {"value": name, "arg": {"row": index}, "update_inputs": True}
                )
            table.rows = table.rows  # trigger update
            table.update_gui()

        def set_selected_maxh():
            maxh = self.change_maxh.model_value
            table = self.shapetype_tables[self.shapetype_selector.model_value]
            for index in table.selected:
                table.set_maxh(
                    {"value": maxh, "arg": {"row": index}, "update_inputs": True}
                )
            table.update_gui()

        def set_selected_visible():
            visible = self.change_visiblity.model_value
            table = self.shapetype_tables[self.shapetype_selector.model_value]
            for index in table.selected:
                table.set_visible(
                    {"value": visible, "arg": {"row": index}, "update_inputs": True}
                )

        def reset_change_for_all():
            self.change_name.model_value = None
            self.change_maxh.model_value = None

        self.change_name = QInput(label="Name", debounce=500).on_update_model_value(
            set_selected_name
        )
        self.change_maxh = NumberInput(
            label="Maxh", debounce=500
        ).on_update_model_value(set_selected_maxh)
        for table in self.shapetype_tables.values():
            table.select_row_callback.append(reset_change_for_all)

        self.change_visiblity = QCheckbox(
            label="Visible",
            model_value=True,
        ).on_update_model_value(set_selected_visible)

        settings = QCard(
            Centered(self.shapetype_selector),
            self.solid_table,
            self.face_table,
            self.edge_table,
            Row(
                Heading("Change selected:", 6, style="margin:20px"),
                self.change_name,
                self.change_maxh,
                self.change_visiblity,
            ),
            style="margin:10px;padding:10px;",
        )

        generate_mesh_button = QBtn(
            QTooltip("Generate Mesh"),
            fab=True,
            icon="mdi-arrow-right-drop-circle-outline",
            color="primary",
            style="position: fixed; right: 140px; bottom: 20px;",
        ).on_click(self.generate_mesh)

        self.back_to_start = QBtn(
            QTooltip("Restart"),
            fab=True,
            icon="mdi-restart",
            color="primary",
            style="position: fixed; left: 20px; bottom: 20px;",
        )

        self.download_mesh_button = FileDownload(
            QTooltip("Download Mesh"),
            id="download_mesh",
            fab=True,
            icon="download",
            color="primary",
            disable=True,
            style="position: fixed; right: 80px; bottom: 20px;",
        )
        self.global_settings = GlobalMeshingSettings()
        self.loading = QInnerLoading(
            QSpinnerGears(size="100px", color="primary"),
            Centered("Generating Mesh..."),
            showing=True,
            style="z-index:100;"
        )

        self.loading.hidden = True
        self.save_button = QBtn(
            QTooltip("Save"),
            fab=True,
            icon="save",
            color="primary",
            style="position: fixed; right: 20px; bottom: 20px;",
        )

        table_and_gui = QSplitter(model_value=40)
        table_and_gui.slot_before = [settings]
        table_and_gui.slot_after = [Row(webgui_card,self.global_settings)]

        self.children = [
            table_and_gui,
            generate_mesh_button,
            self.download_mesh_button,
            self.back_to_start,
            self.save_button,
            self.loading,
        ]

    def generate_mesh(self):
        import netgen
        import netgen.occ as ngocc

        self.loading.label = "Generating Mesh..."
        self.loading.hidden = False
        # ngocc.ResetGlobalShapeProperties()
        geo = ngocc.OCCGeometry(self.shape)
        mp = self.global_settings.get_meshing_parameters()
        try:
            mesh = geo.GenerateMesh(**mp)
            # TODO: .vol.gz not working yet?
            filename = self.name + ".vol"
            mesh.Save(filename)
            self.download_mesh_button.set_file(filename, file_location=filename)
            self.gui_toggle.model_value = "mesh"
            self.webgui_div.hidden = True
            self.mesh_webgui_div.hidden = False
            self.mesh_webgui.draw(mesh, store=True)
        except netgen.libngpy._meshing.NgException as e:
            print("Error in meshing", e)
            self.alert_dialog.children[1] = str(e)
            self.alert_dialog.show()
        self.loading.hidden = True

    def update_table_visiblity(self):
        shape_type = self.shapetype_selector.model_value
        self.solid_table.hidden = shape_type != "solids"
        self.face_table.hidden = shape_type != "faces"
        self.edge_table.hidden = shape_type != "edges"
        self.shapetype_tables[shape_type].update_gui()

    def build_from_shape(self, shape, name):
        self.shape = shape
        self.name = name
        bb = shape.bounding_box
        self.geo_info.children = [
            "Boundingbox: "
            + f"({bb[0][0]:.2f},{bb[0][1]:.2f},{bb[0][2]:.2f}) - ({bb[1][0]:.2f},{bb[1][1]:.2f},{bb[1][2]:.2f})"
        ]
        face_index = {}
        for i, face in enumerate(self.shape.faces):
            face_index[face] = i
        self.shape.faces.col = (0.7, 0.7, 0.7)
        self.webgui.draw(self.shape)
        self.solid_table.set_shapes(self.shape.solids, face_index=face_index)
        self.face_table.set_shapes(self.shape.faces)
        self.edge_table.set_shapes(self.shape.edges)
        self.hidden = False


class MeshingApp(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo = None
        self.create_layout()

    def create_layout(self):
        self.geo_upload_layout = self.create_geo_upload_layout()
        self.main_layout = MainLayout()
        self.main_layout.back_to_start.on_click(self.restart)
        self.main_layout.save_button.on_click(self.save)
        self.component = Div(self.geo_upload_layout, self.main_layout)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        if self.geo_upload.filename is not None:
            self._update_geometry()

    def _update_geometry(self):
        import os
        self.name = os.path.splitext(self.geo_upload.filename)[-2]
        with self.geo_upload.as_temporary_file as geo_file:
            import netgen.occ as ngocc
            self.main_layout.build_from_shape(
                shape=ngocc.OCCGeometry(str(geo_file)).shape, name=self.name
            )
        self.geo_uploading.hidden = True
        self.geo_upload_layout.hidden = True

    def restart(self):
        if "id" in self.metadata:
            self.metadata.pop("id")
        self.geo_upload.model_value = None
        self.geo_upload.filename = None
        self.geo_upload_layout.hidden = False
        self.main_layout.hidden = True

    def create_geo_upload_layout(self):
        self.geo_upload = FileUpload(
            self,
            id="geo_file",
            label="Upload geometry",
            accept="step,stp,brep",
            error_title="Error in Geometry Upload",
            error_message="Please upload a valid geometry file",
        )
        def set_loading():
            self.geo_uploading.hidden = False
        self.geo_upload.on_update_model_value(set_loading)
        self.geo_upload.on_file_loaded(self._update_geometry)
        welcome_header = Heading(
            "Welcome to the Meshing App!", 6, style="text-align:center;"
        )
        welcome_text = Div(
            Div("a saved case, or upload a geometry file to get started."),
            Div("Currently supported geometry formats: step (*.step, *.stp), brep (*.brep)."),
            style="text-align:center;",
        )

        self.load_dialog = LoadDialog(app=self)

        load_saved_btn = QBtn("Load", push=True, size="xl",
                              color="secondary", style="margin-bottom:10px;margin-top:20px;").on_click(
            self.load_dialog.show,
        )

        self.geo_uploading = QInnerLoading(QSpinnerHourglass(size="100px", color="primary"), Centered("Loading..."), showing=True)
        self.geo_uploading.hidden = True

        return Div(
            welcome_header,
            Centered(load_saved_btn),
            welcome_text,
            Centered(self.geo_upload),
            self.load_dialog,
            self.geo_uploading,
            classes="fixed-center",
        )

    def run(self):
        pass
