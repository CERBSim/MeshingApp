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
            ui_title="Load Geometry",
            ui_pagination={"rowsPerPage": 5},
            ui_columns=[
                {"name": "index", "label": "Index", "field": "index"},
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "name", "label": "Name", "field": "name"},
                {"name": "created", "label": "Created", "field": "created"},
                {"name": "modified", "label": "Modified", "field": "modified"},
            ],
            ui_visible_columns=["name", "created", "modified"],
            ui_style="padding:20px;min-width:700px;",
        )
        self.slot_header = [
            QTr(
                QTh("Name"),
                QTh("Created"),
                QTh("Modified"),
                QTh("Actions"),
                ui_style="position:sticky;top:0;z-index:1;background-color:white;",
            )
        ]
        self.ui_slot_body = self.create_row
        self.dialog = dialog

    def load_simulation(self, event):
        self.dialog.ui_hide()
        print("show loading")
        self.dialog.app.geo_uploading.ui_hidden = False
        file_id = event["arg"]["file_id"]
        res = api.get(f"/model/{file_id}")
        import webapp_frontend

        webapp_frontend.set_file_id(file_id)
        self.dialog.app.load(data=res["data"], metadata=res["metadata"])
        print("hide loading")
        self.dialog.app.geo_uploading.ui_hidden = True

    def delete_simulation(self, event):
        file_id = event["arg"]["file_id"]
        api.delete(f"/files/{file_id}")
        # TODO: can we somehow prevent propagation of on click here to row?
        self.ui_rows = [r for r in self.ui_rows if r["id"] != file_id]

    def create_row(self, props):
        row = props["row"]
        created = datetime.datetime.fromtimestamp(row["created"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        modified = datetime.datetime.fromtimestamp(row["modified"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        delete_btn = QBtn(ui_icon="delete", ui_color="negative", ui_flat=True)
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
        super().ui_show()
        res = api.get("/simulations")
        sims = [
            s
            for s in res
            if s["app_id"] == self.app.metadata["app_id"] and not s["deleted"]
        ]
        for i, s in enumerate(sims):
            s["index"] = i
        self.simulations.ui_rows = sims

class GlobalMeshingSettings(QCard):
    def __init__(self):
        def change_mesh_granularity():
            mp = mesh_options[self.mesh_granularity.ui_model_value]
            self.curvature_safety.ui_model_value = mp["curvaturesafety"]
            self.segments_per_edge.ui_model_value = mp["segmentsperedge"]
            self.grading.ui_model_value = mp["grading"]

        self.mesh_dimension = QBtnToggle(
            ui_options=[{ "label" : "2D Mesh", "value" : 2},
                     { "label" : "3D Mesh", "value" : 3}],
            ui_model_value = 3,
            ui_rounded = True,
            ui_glossy = True)

        self.mesh_granularity = QSelect(
            QTooltip(
                Div(
                    "Predefined meshing settings. Selection changes global settings.",
                    ui_style="max-width:300px;",
                )
            ),
            id="mesh_granularity",
            ui_model_value="moderate",
            ui_options=list(mesh_options.keys()),
            ui_style="padding-left:30px;min-width:200px;",
        ).on_update_model_value(change_mesh_granularity)

        self.maxh = QInput(
            QTooltip(
                Div(
                    "Maximum mesh size. Not strictly enforced (if mesh quality would suffer too much).",
                    ui_style="max-width:300px;",
                )
            ),
            id="maxh",
            ui_label="Maxh",
            ui_type="number",
        )
        self.curvature_safety = NumberInput(
            QTooltip(
                Div(
                    "Factor reducing mesh size depending on curvature radius of the face, meshsize is approximately curvature radius divided by this factor.",
                    ui_style="max-width:300px;",
                )
            ),
            id="curvature_safety",
            ui_model_value=2.0,
            ui_label="Curvature Safety",
        )
        self.segments_per_edge = NumberInput(
            QTooltip(
                Div(
                    "Reduces mesh size, such that each edge is divided at least into this number of segments. Setting to factor less than one sets meshsize to 1/factor * edge length. Leave empty to disable.",
                    ui_style="max-width:300px;",
                )
            ),
            id="segments_per_edge",
            ui_clearable=True,
            ui_label="Segments per Edge",
        )
        self.grading = QSlider(
            ui_model_value=0.3,
            ui_min=0.01,
            ui_max=0.99,
            ui_step=0.01,
            id="grading",
            ui_label=True,
        )

        super().__init__(
            Heading("Global Meshing Settings", 3),
            self.mesh_dimension,
            self.mesh_granularity,
            self.maxh, self.curvature_safety,
                self.segments_per_edge,
                Div(
                    "Grading",
                    QTooltip(
                        Div(
                            "Factor controlling how quickly elements can become coarser close to refined regions. Between 0 and 1, 1 means no grading, 0 means maximum grading.",
                            ui_style="width:300px;",
                        )
                    ),
                    self.grading,
                    ui_class="q-field__label",
                    ui_style="margin-top:10px;width:200px;",
                ),
            id="global_settings",
            ui_style="margin:10px;padding:30px;",
            namespace=True,
        )

    def get_meshing_parameters(self):
        mp = {}
        if self.maxh.ui_model_value:
            mp["maxh"] = float(self.maxh.ui_model_value)
        if self.curvature_safety.ui_model_value:
            mp["curvaturesafety"] = float(self.curvature_safety.ui_model_value)
        if self.segments_per_edge.ui_model_value:
            mp["segmentsperedge"] = float(self.segments_per_edge.ui_model_value)
        if self.grading.ui_model_value:
            mp["grading"] = float(self.grading.ui_model_value)
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
            ui_row_key="index",
            ui_flat=True,
            ui_columns=columns,
            ui_style="min-width: 450px;height:650px;",
            ui_title="Shape Settings",
            ui_pagination={"rowsPerPage": 6 },
            ui_selection="multiple",
        )
        self.shapes = []
        self.selected = []
        self.row_components = {}
        self.ui_slot_body = self.create_row
        self.ui_slot_header = [
            QTr(
                QTh("Index"),
                QTh("Name"),
                QTh("Maxh"),
                QTh("Visible"),
                ui_style="position:sticky;top:0;z-index:1;background-color:white;",
            )
        ]
        self.search_input = QInput(
            ui_name="Search", ui_dense=True, ui_debounce=500
        ).on_update_model_value(self.search)
        self.search_input.ui_slot_append = [QIcon(ui_name="search")]
        self.ui_slot_top_right = [
            self.search_input,
            QBtn("Select All", ui_flat=True).on_click(self.select_all),
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
            self.ui_rows = self.all_rows

        else:
            self.ui_rows = [
                row
                for row in self.all_rows
                if (
                    row["name"] is not None
                    and event["value"].lower() in row["name"].lower()
                )
            ]

    def select_all(self):
        self.selected = list(range(len(self.ui_rows)))
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
                row.ui_style = "background-color: #f0f0f0;"
            else:
                row.ui_style = ""
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
                if self.ui_rows[index]["visible"]:
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
                if not self.ui_rows[index]["visible"]:
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
                if not self.ui_rows[index]["visible"]:
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
        return {"base": super().dump(), "rows": self.ui_rows}

    def load(self, data):
        if "base" in data and data["base"] is not None:
            super().load(data["base"])
        if "rows" in data:
            self._loaded_rows = data["rows"]

    def set_name(self, data):
        self.shapes[data["arg"]["row"]].name = data["value"]
        self.ui_rows[data["arg"]["row"]]["name"] = data["value"]
        if "update_inputs" in data and data["update_inputs"]:
            self.name_inputs[data["arg"]["row"]].ui_model_value = data["value"]

    def set_maxh(self, data):
        maxh = (
            1e99
            if (data["value"] is None or data["value"] == "")
            else float(data["value"])
        )
        self.shapes[data["arg"]["row"]].maxh = maxh
        self.ui_rows[data["arg"]["row"]]["maxh"] = maxh
        if "update_inputs" in data and data["update_inputs"]:
            self.maxh_inputs[data["arg"]["row"]].ui_model_value = data["value"]

    def set_visible(self, data):
        self.ui_rows[data["arg"]["row"]]["visible"] = data["value"]
        if "update_inputs" in data and data["update_inputs"]:
            self.visible_cbs[data["arg"]["row"]].ui_model_value = data["value"]
        self.update_gui()

    def create_row(self, props):
        row = props["row"]

        visible_cb = QCheckbox(ui_model_value=row["visible"]).on_update_model_value(
            self.set_visible, arg={"row": row["index"]}
        )
        name_input = QInput(
            ui_label="Name", ui_debounce=500, ui_model_value=row.get("name", None)
        ).on_update_model_value(self.set_name, arg={"row": row["index"]})
        maxh_val = row.get("maxh", None)
        if maxh_val is not None and maxh_val > 1e98:
            maxh_val = None
        maxh_input = NumberInput(
            ui_label="Maxh",
            ui_model_value=maxh_val,
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
        self.ui_rows = rows
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
        self.ui_hidden = True
        # Webgui needs to be wrapped in div so that hide/show works properly?
        self.webgui = WebguiComponent(id="webgui_geo")
        self.webgui.ui_style = "min-width:500px;height:700px"
        self.webgui_div = Div(self.webgui)
        self.mesh_webgui = WebguiComponent(id="webgui_mesh")
        self.mesh_webgui.ui_style = "min-width:500px;height:700px"
        self.mesh_webgui_div = Div(self.mesh_webgui)
        self.mesh_webgui_div.ui_hidden = True

        def update_gui():
            def mesh_to_geo(args):
                camera_settings = self.mesh_webgui._settings["camera"]
                self.webgui.set_camera(camera_settings)

            def geo_to_mesh(args):
                camera_settings = self.webgui._settings["camera"]
                self.mesh_webgui.set_camera(camera_settings)

            if self.gui_toggle.ui_model_value == "geo":
                self.mesh_webgui.update_camera_settings(mesh_to_geo)
            else:
                self.webgui.update_camera_settings(geo_to_mesh)
            self.webgui_div.ui_hidden = self.gui_toggle.ui_model_value != "geo"
            self.mesh_webgui_div.ui_hidden = self.gui_toggle.ui_model_value != "mesh"

        self.gui_toggle = QBtnToggle(
            ui_push=True,
            ui_model_value="geo",
            ui_options=[
                {"label": "Geometry", "value": "geo"},
                {"label": "Mesh", "value": "mesh"},
            ],
            ui_style="margin-top:40px;",
        ).on_update_model_value(update_gui)

        def click_webgui(args):
            dim = args["value"]["dim"]
            if args["value"]["did_move"]:
                return
            if dim == -1:
                table = self.shapetype_tables[self.shapetype_selector.ui_model_value]
                table.selected = []
                table.color_rows()
                return
                # table.update_selected(table.selected)
            if dim == 2:
                index = args["value"]["index"]
                self.shapetype_selector.ui_model_value = "faces"
                self.update_table_visiblity()
                # TODO: Find a good way to go to the correct page
                self.face_table.ui_firstPage()
                for _ in range(index//self.face_table.ui_pagination["rowsPerPage"]):
                    self.face_table.ui_nextPage()
                self.face_table.click_row(args["value"] | {"arg": {"row": index}})
            if dim == 1:
                index = args["value"]["index"]
                self.shapetype_selector.ui_model_value = "edges"
                self.update_table_visiblity()
                # TODO: Find a good way to go to the correct page
                self.edge_table.ui_firstPage()
                for _ in range(index//self.edge_table.ui_pagination["rowsPerPage"]):
                    self.edge_table.ui_nextPage()
                self.edge_table.click_row(args["value"] | {"arg": {"row": index}})

        self.webgui.on_click(click_webgui)
        self.geo_info = Div(ui_style="padding-left:5px;")
        webgui_card = QCard(
            Centered(self.gui_toggle),
            self.webgui_div,
            self.mesh_webgui_div,
            self.geo_info,
            ui_style="margin:10px; fit;width:700px;height:800px;",
        )
        self.shapetype_selector = QBtnToggle(
            ui_push=True,
            ui_model_value="faces",
            ui_options=[
                {"label": "Solids", "value": "solids"},
                {"label": "Faces", "value": "faces"},
                {"label": "Edges", "value": "edges"},
            ],
            ui_style="margin-bottom:10px;",
        )
        self.shapetype_selector.on_update_model_value(self.update_table_visiblity)
        self.solid_table = ShapeTable(self.webgui, "solids")
        self.solid_table.ui_hidden = True
        self.face_table = ShapeTable(self.webgui, "faces")

        def create_body_cell(props):
            return [QTd(QInput(ui_label=props["col"]["label"]))]

        self.face_table.ui_slot_body_cell_name("name", create_body_cell)

        self.edge_table = ShapeTable(self.webgui, "edges")
        self.edge_table.ui_hidden = True
        self.shapetype_tables = {
            "solids": self.solid_table,
            "faces": self.face_table,
            "edges": self.edge_table,
        }

        def set_selected_name():
            name = self.change_name.ui_model_value
            table = self.shapetype_tables[self.shapetype_selector.ui_model_value]
            for index in table.selected:
                table.set_name(
                    {"value": name, "arg": {"row": index}, "update_inputs": True}
                )
            table.ui_rows = table.ui_rows  # trigger update
            table.update_gui()

        def set_selected_maxh():
            maxh = self.change_maxh.ui_model_value
            table = self.shapetype_tables[self.shapetype_selector.ui_model_value]
            for index in table.selected:
                table.set_maxh(
                    {"value": maxh, "arg": {"row": index}, "update_inputs": True}
                )
            table.update_gui()

        def set_selected_visible():
            visible = self.change_visiblity.ui_model_value
            table = self.shapetype_tables[self.shapetype_selector.ui_model_value]
            for index in table.selected:
                table.set_visible(
                    {"value": visible, "arg": {"row": index}, "update_inputs": True}
                )

        def reset_change_for_all():
            self.change_name.ui_model_value = None
            self.change_maxh.ui_model_value = None

        self.change_name = QInput(ui_label="Name", ui_debounce=500).on_update_model_value(
            set_selected_name
        )
        self.change_maxh = NumberInput(
            ui_label="Maxh", ui_debounce=500
        ).on_update_model_value(set_selected_maxh)
        for table in self.shapetype_tables.values():
            table.select_row_callback.append(reset_change_for_all)

        self.change_visiblity = QCheckbox(
            ui_label="Visible",
            ui_model_value=True,
        ).on_update_model_value(set_selected_visible)

        settings = QCard(
            Centered(self.shapetype_selector),
            self.solid_table,
            self.face_table,
            self.edge_table,
            Row(
                Heading("Change selected:", 6, ui_style="margin:20px"),
                self.change_name,
                self.change_maxh,
                self.change_visiblity,
            ),
            ui_style="margin:10px;padding:10px;",
        )

        generate_mesh_button = QBtn(
            QTooltip("Generate Mesh"),
            ui_fab=True,
            ui_icon="mdi-arrow-right-drop-circle-outline",
            ui_color="primary",
            ui_style="position: fixed; right: 140px; bottom: 20px;",
        ).on_click(self.generate_mesh)

        self.back_to_start = QBtn(
            QTooltip("Restart"),
            ui_fab=True,
            ui_icon="mdi-restart",
            ui_color="primary",
            ui_style="position: fixed; left: 20px; bottom: 20px;",
        )

        self.download_mesh_button = FileDownload(
            QTooltip("Download Mesh"),
            id="download_mesh",
            ui_fab=True,
            ui_icon="download",
            ui_color="primary",
            ui_disable=True,
            ui_style="position: fixed; right: 80px; bottom: 20px;",
        )
        self.global_settings = GlobalMeshingSettings()
        self.loading = QInnerLoading(
            QSpinnerGears(ui_size="100px", ui_color="primary"),
            Centered("Generating Mesh..."),
            ui_showing=True,
            ui_style="z-index:100;"
        )

        self.loading.ui_hidden = True
        self.save_button = QBtn(
            QTooltip("Save"),
            ui_fab=True,
            ui_icon="save",
            ui_color="primary",
            ui_style="position: fixed; right: 20px; bottom: 20px;",
        )

        table_and_gui = QSplitter(ui_model_value=40)
        table_and_gui.ui_slot_before = [settings]
        table_and_gui.ui_slot_after = [Row(webgui_card,self.global_settings)]

        self.ui_children = [
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
        self.mesh = None

        self.loading.ui_label = "Generating Mesh..."
        self.loading.ui_hidden = False
        # ngocc.ResetGlobalShapeProperties()
        geo = ngocc.OCCGeometry(self.shape,
                                dim=self.global_settings.mesh_dimension.ui_model_value)
        mp = self.global_settings.get_meshing_parameters()
        try:
            mesh = geo.GenerateMesh(**mp)
            # TODO: .vol.gz not working yet?
            filename = self.name + ".vol"
            mesh.Save(filename)
            self.mesh = mesh
            self.download_mesh_button.set_file(filename, file_location=filename)
            self.gui_toggle.ui_model_value = "mesh"
            self.webgui_div.ui_hidden = True
            self.mesh_webgui_div.ui_hidden = False
            self.mesh_webgui.draw(mesh, store=True)
            self.webgui.clear()
        except netgen.libngpy._meshing.NgException as e:
            print("Error in meshing", e)
            self.alert_dialog.ui_children[1] = str(e)
            self.alert_dialog.ui_show()
        self.loading.ui_hidden = True

    def update_table_visiblity(self):
        shape_type = self.shapetype_selector.ui_model_value
        self.solid_table.ui_hidden = shape_type != "solids"
        self.face_table.ui_hidden = shape_type != "faces"
        self.edge_table.ui_hidden = shape_type != "edges"
        self.shapetype_tables[shape_type].update_gui()

    def build_from_shape(self, shape, name):
        self.shape = shape
        self.name = name
        bb = shape.bounding_box
        self.geo_info.ui_children = [
            "Boundingbox: "
            + f"({bb[0][0]:.2f},{bb[0][1]:.2f},{bb[0][2]:.2f}) - ({bb[1][0]:.2f},{bb[1][1]:.2f},{bb[1][2]:.2f})"
        ]
        size = sum((bb[1][i] - bb[0][i])**2 for i in range(3))**0.5
        face_index = {}
        for i, face in enumerate(self.shape.faces):
            face_index[face] = i
        self.shape.faces.col = (0.7, 0.7, 0.7)
        self.webgui.draw(self.shape)
        if len(self.shape.solids) == 0:
            self.shapetype_selector.ui_options = [
                {"label": "Faces", "value": "faces"},
                {"label": "Edges", "value": "edges"},
            ]
            if not any([abs(v.p[2]) > size * 1e-10 for v in self.shape.vertices]):
                self.global_settings.mesh_dimension.ui_model_value = 2
                self.global_settings.mesh_dimension.ui_disable = False
            else:
                self.global_settings.mesh_dimension.ui_disable = True
        else:
            self.global_settings.mesh_dimension.ui_model_value = 3
            self.global_settings.mesh_dimension.ui_disable = True
            self.shapetype_selector.ui_options = [
                {"label": "Solids", "value": "solids"},
                {"label": "Faces", "value": "faces"},
                {"label": "Edges", "value": "edges"},
            ]
        self.solid_table.set_shapes(self.shape.solids, face_index=face_index)
        self.face_table.set_shapes(self.shape.faces)
        self.edge_table.set_shapes(self.shape.edges)
        self.ui_hidden = False


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
        self.geo_uploading.ui_hidden = True
        self.geo_upload_layout.ui_hidden = True

    def load(self, *args, **kwargs):
        super().load(*args, **kwargs)


    def restart(self):
        if "id" in self.metadata:
            self.metadata.pop("id")
        self.geo_upload.ui_model_value = None
        self.geo_upload.filename = None
        self.geo_upload_layout.ui_hidden = False
        self.main_layout.ui_hidden = True

    def create_geo_upload_layout(self):
        self.geo_upload = FileUpload(
            id="geo_file",
            ui_label="Upload geometry",
            ui_accept="step,stp,brep",
            ui_error_title="Error in Geometry Upload",
            ui_error_message="Please upload a valid geometry file",
        )
        def set_loading():
            self.geo_uploading.ui_hidden = False
        self.geo_upload.on_update_model_value(set_loading)
        self.geo_upload.on_file_loaded(self._update_geometry)
        welcome_header = Heading(
            "Welcome to the Meshing App!", 6, ui_style="text-align:center;"
        )
        welcome_text = Div(
            Div("a saved case, or upload a geometry file to get started."),
            Div("Currently supported geometry formats: step (*.step, *.stp), brep (*.brep)."),
            ui_style="text-align:center;",
        )

        self.load_dialog = LoadDialog(app=self)

        load_saved_btn = QBtn("Load", ui_push=True, ui_size="xl",
                              ui_color="secondary", ui_style="margin-bottom:10px;margin-top:20px;").on_click(
            self.load_dialog.ui_show,
        )

        self.geo_uploading = QInnerLoading(QSpinnerHourglass(ui_size="100px", ui_color="primary"), Centered("Loading..."), ui_showing=True)
        self.geo_uploading.ui_hidden = True

        return Div(
            welcome_header,
            Centered(load_saved_btn),
            welcome_text,
            Centered(self.geo_upload),
            self.load_dialog,
            self.geo_uploading,
            id="geo_upload_layout",
            ui_class="fixed-center",
        )

    def run(self):
        pass
