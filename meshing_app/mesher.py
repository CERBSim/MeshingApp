
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
    s = Draw(geo.shape)
    json.dump(s.GetData(), open("render_data.json", "w"))

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

    @staticmethod
    async def upload(dir_, file):
        os.makedirs(dir_, exist_ok=True)
        geofile = GeometryFile(path=dir_)
        save_upload_file(file, geofile.path("original.step"))
        runRoutine(preprocessGeometry, cwd=geofile.path())
        
class GeometryUpload(ParameterStep):
    def __init__(self, name="Geometry Upload"):
        super().__init__(name=name)
        self.name = name
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


class GeometryStep(Step):
    def __init__(self, geo_file_id=None, name="Geometry"):
        self.name = name
        self.geo_file_id = geo_file_id
        self.render_data = None
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
                 "data" : { "geo_file_id" : self.geo_file_id,
                            "render_data" : self.render_data,
                            "add_enclosing_domain" : self.add_enclosing_domain } }
    

@register_application
class MeshingModel(BaseModel):
    modelName = "Meshing"
    modelVersion = __version__
    modelGroup = 'cerbsim'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geo_upload = GeometryUpload()
        geo_upload_update = self.geo_upload.update
        self.geo_step = GeometryStep()
        def update_render_data(*args, **kwargs):
            geo_upload_update(*args, **kwargs)
            self.geo_step.render_data = self.geo_upload.geo_file.get_file().getRenderData()
        self.geo_upload.update = update_render_data
        self.steps = [self.geo_upload, self.geo_step]

    def run(self, result_dir):
        # save outputs to dir
        pass

    @staticmethod
    def getDescription():
        return "Create mesh from uploaded geometry to be used in further simulations"

    
