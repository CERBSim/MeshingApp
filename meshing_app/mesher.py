from webapp.applications.base import (
    BaseModel,
    DrawPNG,
    generateHTML,
    MakeHTMLScreenshot,
)
from webapp.applications.parameters import *
from webapp.applications.steps import *
from webapp.applications import register_application
from .version import __version__
from webapp.filetype import register_filetype, SpecialFile, save_upload_file
from webapp.routines import runRoutine, register_routine
from webapp.utils import time_now, load_image
from webapp.applications.run import upload_file

import json
import os
import pickle

# TODO: Needs concept of "live resource" that uses available floating computing power for meshing,...


@register_routine
def runGeometry(
    geo_file,
    exterior,
    diam=None,
    glue_solids=False,
    nr=0,
    write_render_data=True,
    write_step=True,
    create_image=False,
):
    from netgen.occ import OCCGeometry, Glue, Box, Sphere
    from netgen.webgui import Draw

    geo = OCCGeometry(geo_file)
    shape = geo.shape
    if glue_solids:
        shape = Glue(shape.solids)
    if exterior is not None:
        bb = shape.bounding_box
        d = bb[1] - bb[0]
        if exterior == "box":
            ext = Box(bb[0] - (diam - 1) / 2 * d, bb[1] + (diam - 1) / 2 * d)
        elif exterior == "sphere":
            ext = Sphere(bb[0] + 0.5 * d, d.Norm() * diam / 2)
        else:
            raise Exception(f"Exterior {exterior} unknown")
        ext -= shape
        shape = Glue([shape, ext])
    for f in shape.faces:
        f.col = (0.7, 0.7, 0.7)
    s = Draw(shape)

    if write_render_data:
        json.dump(s.GetData(), open(f"render_data_{nr}.json", "w"))
    bb = shape.bounding_box
    diam = bb[1] - bb[0]
    data = {
        "parameters": {
            "Diameter": f"{diam.Norm():0.2f}",
            "Length (x-Axis)": f"{diam.x:0.2f}",
            "Depth (y-Axis)": f"{diam.y:0.2f}",
            "Height (z-Axis)": f"{diam.z:0.2f}",
            "Unit": "mm",
            "Number of Solids" : len(shape.solids),
            "Number of Faces" : len(set(shape.faces)),
            "Number of Edges" : len(set(shape.edges)),
            "Number of Vertices" : len(set(shape.vertices))
        }
    }
    if create_image:
        generateHTML(json.dumps(s.GetData()), "tmp.html")
        MakeHTMLScreenshot("tmp.html", width=400, height=400)
        img = load_image("tmp.png")
        data["image"] = img

    json.dump(data, open("data", "w"))
    if write_step:
        # Step writing is buggy - better pickle (internal brep + our data)
        pickle.dump(OCCGeometry(shape), file=open("modified.geo", "wb"))


@register_filetype
class GeometryFile(SpecialFile):
    _type = "mesher_geo"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_type = "mesher_geo"

    def get_file_name(self):
        return self.path("original.step")

    @staticmethod
    async def upload(dir_, file):
        os.makedirs(dir_, exist_ok=True)
        geofile = GeometryFile(path=dir_)
        save_upload_file(file, geofile.path("original.step"))
        runRoutine(
            runGeometry,
            cwd=geofile.path(),
            geo_file="original.step",
            exterior=None,
            write_render_data=False,
            write_step=False,
            create_image=True,
        )


class GeometryUpload(ParameterStep):
    def __init__(self, path, name="Geometry Upload"):
        super().__init__(name=name)
        self.name = name
        self.path = path
        # self.geo_file = FileParameter(filetype="mesher_geo",
        #                               name="STEP-File",
        #                               file_endings=[".step"])
        self.geo_file = SpecialFileParameter(
            "mesher_geo", "STEP-File", file_extensions=[".step"]
        )

        self.ext_box = FloatParameter("Diameter (times geo size)", default=3)
        self.ext_sphere = FloatParameter("Diameter (times geo size)", default=3)

        self.exterior_domain = SelectionDialog(
            "Add exterior domain",
            options=["None", "Box", "Sphere"],
            parameters=[Label(""), self.ext_box, self.ext_sphere],
            value="None"
        )

        self.shell_or_2d = SelectionDialog(
            name=None,
            options=["2D Geometry", "3D Shell"],
            value="2D Geometry",
            variant="buttons",
        )

        def updateVisiblityShellOr2d():
            f = self.geo_file.get_file()
            if f is not None:
                data = f.load()
                if "Number of Solids" in data["parameters"]:
                    self.shell_or_2d.visible = (
                        data["parameters"]["Number of Solids"] == 0
                    )
                else:
                    self.shell_or_2d.visible = False
            else:
                self.shell_or_2d.visible = False

        self.geo_file.on_update = updateVisiblityShellOr2d

        self.glue_solids = Switch("Glue solids", default=False)
        self.parameters = [
            self.geo_file,
            self.shell_or_2d,
            self.glue_solids,
            self.exterior_domain,
        ]
        self.last_data = self.get_input_data()

    def get_dynamic_data(self):
        return { **super().get_dynamic_data() }

    def validate(self):
        if self.geo_file.value is None:
            raise Exception("No geometry selected!")

    def update(self, data, *args, **kwargs):
        nr = 0
        ts_file = self.path(f"render_data_{nr}.json.timestamp")
        if os.path.exists(ts_file):
            old_timestamp = open(ts_file).read()
        else:
            old_timestamp = None
        super().update(data, *args, **kwargs)
        if self._initial_update:
            self.geo_file.on_update()
        # TODO: Find a cleaner way of doing a timestamp (python hash function doesn't work)
        timestamp = json.dumps(self.get_input_data())
        print("timestamp\n", timestamp, "\n", old_timestamp)
        if timestamp != old_timestamp and not self._initial_update:
            print("rebuild render data", self.path(), self.geo_file.get_file().get_file_name())
            exterior = None
            diam = 3
            if self.exterior_domain.IsSelected(1):
                exterior = "box"
                diam = self.ext_box.value
            elif self.exterior_domain.IsSelected(2):
                exterior = "sphere"
                diam = self.ext_sphere.value
            runRoutine(
                runGeometry,
                cwd=self.path(),
                geo_file=self.geo_file.get_file().get_file_name(),
                exterior=exterior,
                diam=diam,
                nr=nr,
                glue_solids=self.glue_solids.value,
            )
            open(ts_file, "w").write(timestamp)

class GeometryStep(Step):
    def __init__(self, upload_step, name="Geometry"):
        super().__init__(name=name)
        self.upload_step = upload_step
        self.materials = []
        self.boundaries = []
        self.edge_names = []
        self.meshsize_solids = []
        self.meshsize_faces = []
        self.meshsize_edges = []
        self._render_data = None

    def update(self, data, db=None, **kwargs):
        print("update geometry step", data)
        if "solid_names" in data:
            self.materials = data["solid_names"]
        if "names" in data:
            self.boundaries = data["names"]
        if "edge_names" in data:
            self.edge_names = data["edge_names"]
        if "meshsize_solids" in data:
            self.meshsize_solids = data["meshsize_solids"]
        if "meshsize_faces" in data:
            self.meshsize_faces = data["meshsize_faces"]
        if "meshsize_edges" in data:
            self.meshsize_edges = data["meshsize_edges"]

    def get_static_data(self):
        return {
            **super().get_static_data(),
            "type": "Geometry",
            }

    def get_input_data(self):
        return {
            **super().get_input_data(),
            "solid_names": self.materials,
            "names": self.boundaries,
            "edge_names": self.edge_names,
            "meshsize_solids": self.meshsize_solids,
            "meshsize_faces": self.meshsize_faces,
            "meshsize_edges": self.meshsize_edges,
        }


@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = "default"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_upload = GeometryUpload(self.model_file.path)
        self.geo_step = GeometryStep(self.geo_upload)
        self.granularity = SelectionDialog(
            "Granularity",
            ["Default", "Very Coarse", "Coarse", "Moderate", "Fine", "Very Fine"],
            variant="buttons",
        )
        self.maxh = FloatParameter("Max Meshsize", default=None)
        self.grading = FloatParameter(
            "Grading",
            default=0.3,
            info="Limits how fast elements can grow away from local refinement. From 0 to 1, with 0 constant fine element size and 1 immediatly allowing as coarse as possible",
        )
        self.curvaturesafety = FloatParameter(
            "Curvature Safety",
            default=2,
            info="On curved surfaces restrict meshisize to value times radius",
        )
        self.segmentsperedge = FloatParameter(
            "Segments per edge",
            default=1,
            info="Restict meshsize on edges to value times edge length. To disable set to 0.",
        )
        self.closeedgefac = FloatParameter(
            "Close edge factor",
            default=0,
            info="Restrict meshsize if edges come close to each other (but do not join in a vertex). Disable by setting to 0.",
        )

        def updateGranularity():
            if self.granularity.value == "Very Coarse":
                self.grading.value = 0.7
                self.curvaturesafety.value = 1
                self.closeedgefac.value = 0
                self.segmentsperedge.value = 0.3
                return
            if self.granularity.value == "Coarse":
                self.grading.value = 0.5
                self.curvaturesafety.value = 1.5
                self.closeedgefac.value = 0
                self.segmentsperedge.value = 0.5
                return
            if self.granularity.value == "Default":
                self.grading.value = 0.3
                self.curvaturesafety.value = 2
                self.closeedgefac.value = 0
                self.segmentsperedge.value = 1
                return
            if self.granularity.value == "Moderate":
                self.grading.value = 0.3
                self.curvaturesafety.value = 2
                self.closeedgefac.value = 2
                self.segmentsperedge.value = 1
                return
            if self.granularity.value == "Fine":
                self.grading.value = 0.2
                self.curvaturesafety.value = 3
                self.closeedgefac.value = 3.5
                self.segmentsperedge.value = 2
                return
            if self.granularity.value == "Very Fine":
                self.grading.value = 0.1
                self.curvaturesafety.value = 5
                self.closeedgefac.value = 5
                self.segmentsperedge.value = 3
                return

        self.granularity.on_update = updateGranularity

        self.mparam_step = ParameterStep(
            name="Meshing Parameters",
            parameters=[
                self.granularity,
                self.maxh,
                self.grading,
                self.curvaturesafety,
                self.segmentsperedge,
                self.closeedgefac,
            ],
        )
        self.steps = [self.geo_upload, self.geo_step, self.mparam_step]
        self.mesh = None

    def run(self, result_dir):
        from netgen.occ import OCCGeometry
        from ngsolve import Mesh, Draw

        geo = pickle.load(open(self.model_file.path("modified.geo"), "rb"))
        shape = geo.shape
        mats = self.geo_step.materials
        maxh = self.geo_step.meshsize_solids
        for i, s in enumerate(shape.solids):
            if len(mats) > i and mats[i] is not None:
                s.name = mats[i]
            if len(maxh) > i and maxh[i] is not None:
                s.maxh = maxh[i]
        bnds = self.geo_step.boundaries
        maxh = self.geo_step.meshsize_faces
        unique_faces = []
        for f in shape.faces:
            if f not in unique_faces:
                unique_faces.append(f)
        for i, f in enumerate(unique_faces):
            if len(bnds) > i and bnds[i] is not None:
                f.name = bnds[i]
            if len(maxh) > i and maxh[i] is not None:
                f.maxh = maxh[i]
        enames = self.geo_step.edge_names
        maxh = self.geo_step.meshsize_edges
        unique_edges = []
        for e in shape.edges:
            if e not in unique_edges:
                unique_edges.append(e)
        for i, e in enumerate(unique_edges):
            if len(enames) > i and enames[i] is not None:
                e.name = enames[i]
            if len(maxh) > i and maxh[i] is not None:
                e.maxh = maxh[i]

        kwargs = {
            "grading": self.grading.value,
            "curvaturesafety": self.curvaturesafety.value,
            "segmentsperedge": self.segmentsperedge.value,
            "closeedgefac": self.closeedgefac.value,
        }
        if self.maxh.value is not None:
            kwargs["maxh"] = self.maxh.value
        dim = 3
        if (
            len(shape.solids) == 0
            and self.geo_upload.shell_or_2d.value == "2D Geometry"
        ):
            dim = 2
        geo = OCCGeometry(shape, dim=dim)
        Draw(geo)
        try:
            mesh = geo.GenerateMesh(**kwargs)
            self.meshing_failed = False
            mesh.Save(os.path.join(result_dir, "mesh.vol.gz"))
            upload_file(
                name=self.model_file.name + ".vol.gz",
                filepath=os.path.join(result_dir, "mesh.vol.gz"),
                filetype="mesh",
            )
            self.mesh = Mesh(mesh)
        except Exception as e:
            if str(e) == "Meshing failed!":
                print("Meshing failed")
                self.meshing_failed = True
                # TODO: Visualize failed part of mesh
                # import netgen.libngpy._meshing as nm

                # self.mesh = Mesh(nm._GetGlobalMesh())
            else:
                raise e
        self.info = {
            "ne": self.mesh.ne,
            "nse": self.mesh.nface,
        }

    def getReportTemplate(self):
        ne, nse = self.info["ne"], self.info["nse"]
        if self.meshing_failed:
            # TODO: Show region of problem (together with edge mesh)
            return """
# Meshing failed!

TODO: Visualize problem region

"""
        else:
            return """
# Mesh Result

## Download

[[download]]

## Info

|                  |       |
|------------------|:------|
| Elements         | {ne}  |
| Surface Elements | {nse} |

[[mesh]]
""".format(
                ne=ne, nse=nse
            )

    def RenderObject(self, what):
        if what == "mesh":
            self.mesh.Curve(3)
            return DrawPNG(what, self.mesh)
        if what == "download":
            return {"type": "download", "what": "mesh"}

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"
