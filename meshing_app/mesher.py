
from webapp.applications.base import BaseModel, DrawPNG, generateHTML, \
    MakeHTMLScreenshot
from webapp.applications.parameters import *
from webapp.applications.steps import *
from webapp.applications import register_application
from .version import __version__
from webapp.filetype import register_filetype, SpecialFile, save_upload_file
from webapp.routines import runRoutine, register_routine
from webapp.utils import time_now, load_image

import json
import os

# TODO: Needs concept of "live resource" that uses available floating computing power for meshing,...

@register_routine
def runGeometry(geo_file, exterior, diam=None, glue_solids=False, nr=0,
                write_render_data=True, write_step=True,
                create_image=False):
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
            ext = Box(bb[0] - (diam-1)/2 * d, bb[1] + (diam-1)/2 * d)
        elif exterior == "sphere":
            ext = Sphere(bb[0] + 0.5 * d, d.Norm() * diam/2)
        else:
            raise Exception(f"Exterior {exterior} unknown")
        ext -= shape
        shape = Glue([shape, ext])
    for f in shape.faces:
        f.col = (0.7,0.7,0.7)
    s = Draw(shape)

    if write_render_data:
        json.dump(s.GetData(), open(f"render_data_{nr}.json", "w"))
    bb = shape.bounding_box
    diam = (bb[1]-bb[0])
    data = { "parameters" : { "Diameter" : f"{diam.Norm():0.2f}",
                                "Length (x-Axis)" : f"{diam.x:0.2f}",
                                "Depth (y-Axis)" : f"{diam.y:0.2f}",
                                "Height (z-Axis)" : f"{diam.z:0.2f}",
                                "Unit" : "mm" } }
    if create_image:
        generateHTML(json.dumps(s.GetData()), "tmp.html")
        MakeHTMLScreenshot("tmp.html", width=400, height=400)
        img = load_image("tmp.png")
        data["image"] = img

    json.dump(data, open("data", "w"))
    if write_step:
        shape.WriteStep("geo.step")

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
        runRoutine(runGeometry, cwd=geofile.path(),
                   geo_file="original.step",
                   exterior=None, write_render_data=False,
                   write_step=False, create_image=True)


class GeometryUpload(ParameterStep):
    def __init__(self, path, name="Geometry Upload"):
        super().__init__(name=name)
        self.name = name
        self.path = path
        # self.geo_file = FileParameter(filetype="mesher_geo",
        #                               name="STEP-File",
        #                               file_endings=[".step"])
        self.geo_file = SpecialFileParameter("mesher_geo",
                                             "STEP-File",
                                             title="Select Geometry",
                                             file_extensions=".step")

        self.ext_box = FloatParameter("Diameter (times geo size)",
                                      default=3)
        self.ext_sphere = FloatParameter("Diameter (times geo size)",
                                      default=3)

        self.exterior_domain = Selector("Add exterior domain",
                                        options=["None",
                                                 "Box",
                                                 "Sphere"],
                                        parameters=[[],
                                                    [self.ext_box],
                                                    [self.ext_sphere]],
                                        selected=[True, False, False])
        self.glue_solids = Switch("Glue solids", default=False)
        self.parameters = [self.geo_file, self.glue_solids, self.exterior_domain]
        self.last_data = self.get_data()["data"]

    def update(self, data, *args, **kwargs):
        super().update(data, *args, **kwargs)
        dat = self.get_data()["data"]
        if dat != self.last_data and not self._initial_update:
            exterior = None
            diam = 3
            if self.exterior_domain.selected[1]:
                exterior = "box"
                diam = self.ext_box.value
            elif self.exterior_domain.selected[2]:
                exterior = "sphere"
                diam = self.ext_sphere.value
            runRoutine(runGeometry, cwd=self.path(),
                       geo_file=self.geo_file.get_file().get_file_name(),
                       exterior=exterior, diam=diam, glue_solids=self.glue_solids.value)
        self.last_data = dat

class GeometryStep(Step):
    def __init__(self, upload_step, name="Geometry"):
        self.name = name
        self.upload_step = upload_step
        self.materials = []
        self.boundaries = []
        self.meshsize_solids = []
        self.meshsize_faces = []
        self._render_data = None

    def update(self, data, db=None, **kwargs):
        data = data["data"]
        if "solid_names" in data:
            self.materials = data["solid_names"]
        if "names" in data:
            self.boundaries = data["names"]
        if "meshsize_solids" in data:
            self.meshsize_solids = data["meshsize_solids"]
        if "meshsize_faces" in data:
            self.meshsize_faces = data["meshsize_faces"]

    def get_data(self):
        return { "type" : "Geometry",
                 "name" : self.name,
                 "data" : { "solid_names" : self.materials,
                            "names" : self.boundaries,
                            "meshsize_solids" : self.meshsize_solids,
                            "meshsize_faces" : self.meshsize_faces } }


@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = 'cerbsim'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_upload = GeometryUpload(self.model_file.path)
        self.geo_step = GeometryStep(self.geo_upload)
        self.granularity = SelectionDialog("Granularity",
                                           ["Default",
                                            "Very Coarse",
                                            "Coarse",
                                            "Moderate",
                                            "Fine",
                                            "Very Fine"])
        self.maxh = FloatParameter("Max Meshsize", default=None)
        self.grading = FloatParameter("Grading", default=0.3)

        def updateGranularity():
            if self.granularity.selected == "Very Coarse":
                self.grading.value = 0.7
                return
            if self.granularity.selected == "Coarse":
                self.grading.value = 0.5
                return
            if self.granularity.selected == "Default":
                self.grading.value = 0.3
                return
            if self.granularity.selected == "Moderate":
                self.grading.value = 0.3
                return
            if self.granularity.selected == "Fine":
                self.grading.value = 0.2
                return
            if self.granularity.value == "Very Fine":
                self.grading.value = 0.1
                return
        self.granularity.on_update = updateGranularity

        self.mparam_step = ParameterStep(name="Meshing Parameters",
                                         parameters=[self.granularity,
                                                     self.maxh,
                                                     self.grading])
        self.steps = [self.geo_upload, self.geo_step, self.mparam_step]

    def run(self, result_dir):
        from netgen.occ import OCCGeometry
        from netgen.meshing import MeshingParameters
        from ngsolve import Mesh
        geo = OCCGeometry(self.model_file.path("geo.step"))
        shape = geo.shape
        mats = self.geo_step.materials
        maxh = self.geo_step.meshsize_solids
        for i, s in enumerate(shape.solids):
            if mats is not None and mats[i] is not None:
                s.name = mats[i]
            if maxh is not None and maxh[i] is not None:
                s.maxh = maxh[i]
        bnds = self.geo_step.boundaries
        maxh = self.geo_step.meshsize_faces
        for i, f in enumerate(shape.faces):
            if bnds is not None and bnds[i] is not None:
                f.name = bnds[i]
            if maxh is not None and maxh[i] is not None:
                f.maxh = maxh[i]
        kwargs = {}
        if self.maxh.value is not None:
            kwargs["maxh"] = self.maxh.value
        kwargs["grading"] = self.grading.value
        geo = OCCGeometry(shape)
        mesh = geo.GenerateMesh(**kwargs)
        mesh.Save(os.path.join(result_dir, "mesh.vol.gz"))
        self.mesh = Mesh(mesh)
        self.info = { "ne" : self.mesh.ne,
                      "nse" : self.mesh.nface,
                      }

    def getReportTemplate(self):
        ne, nse = self.info["ne"], self.info["nse"]
        return """
# Mesh Result

Number of Elements: {ne}
Number of Surface Elements: {nse}

[[mesh]]
""".format(ne=ne, nse=nse)

    def RenderObject(self, what):
        if what == "mesh":
            return DrawPNG(what, self.mesh)

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"
