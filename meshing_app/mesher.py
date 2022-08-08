
from webapp.applications.base import BaseModel
from webapp.applications.parameters import *
from webapp.applications.steps import *
from webapp.applications import register_application
from .version import __version__
from webapp.filetype import register_filetype, SpecialFile, save_upload_file
from webapp.routines import runRoutine, register_routine

import json

from netgen.occ import OCCGeometry

# TODO: Needs concept of "live resource" that uses available floating computing power for meshing,...

@register_routine
def preprocessGeometry():
    from netgen.occ import OCCGeometry
    from netgen.webgui import Draw
    geo = OCCGeometry("original.step")
    shape = geo.shape
    s = Draw(shape)
    json.dump(s.GetData(), open("render_data.json", "w"))

@register_routine
def runGeometry(geo_file, exterior=None, diam=None):
    from netgen.occ import OCCGeometry, Glue, Box, Sphere
    from netgen.webgui import Draw
    print("run geometry with ", geo_file, exterior, diam)
    geo = OCCGeometry(geo_file)
    shape = geo.shape
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
    s = Draw(shape)
    json.dump(s.GetData(), open("geo_render_data.json", "w"))
    shape.WriteStep("geo.step")

@register_filetype
class GeometryFile(SpecialFile):
    _type = "mesher_geo"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_type = "mesher_geo"

    def getRenderData(self):
        if os.path.exists(self.path("render_data.json")):
            return json.load(open(self.path("render_data.json")))
        return None

    def get_file_name(self):
        return self.path("original.step")

    @staticmethod
    async def upload(dir_, file):
        os.makedirs(dir_, exist_ok=True)
        geofile = GeometryFile(path=dir_)
        save_upload_file(file, geofile.path("original.step"))
        runRoutine(preprocessGeometry, cwd=geofile.path())
        
class GeometryUpload(ParameterStep):
    def __init__(self, path, name="Geometry Upload"):
        super().__init__(name=name)
        self.name = name
        self.path = path
        print("model path =", self.path)
        self.geo_file = FileParameter(filetype="mesher_geo",
                                      name="STEP-File",
                                      file_endings=[".step"])

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
        self.parameters = [self.geo_file, self.exterior_domain]
        self.last_data = self.get_data()["data"]

    @property
    def render_data(self):
        if os.path.exists(self.path("geo_render_data.json")):
            return json.load(open(self.path("geo_render_data.json")))
        return None

    def update(self, data, *args, **kwargs):
        super().update(data, *args, **kwargs)
        dat = self.get_data()["data"]
        print("dat =", dat)
        print("last dat = ", self.last_data)
        if dat != self.last_data and not self._initial_update:
            print("changed data")
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
                       exterior=exterior, diam=diam)
        self.last_data = dat

class GeometryStep(Step):
    def __init__(self, upload_step, name="Geometry"):
        self.name = name
        self.upload_step = upload_step
        self.materials = []
        self.boundaries = []
        self.add_enclosing_domain = None

    def update(self, data, db=None, **kwargs):
        pass

    def get_geometry(self):
        pass

    def get_data(self):
        return { "type" : "Geometry",
                 "name" : self.name,
                 "data" : { "render_data" : self.upload_step.render_data,
                            "add_enclosing_domain" : self.add_enclosing_domain } }
    

@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = 'cerbsim'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_upload = GeometryUpload(self.model_file.path)
        self.geo_step = GeometryStep(self.geo_upload)
        self.steps = [self.geo_upload, self.geo_step]

    def run(self, result_dir):
        # save outputs to dir
        pass

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"

    
