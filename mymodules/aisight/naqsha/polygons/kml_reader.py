import re
from collections import namedtuple
import xml.etree.ElementTree as ET


Coordinates = namedtuple("Coordinates", ["longitude", "latitude"])
to_coordinates = lambda c: Coordinates(longitude=float(c[0]), latitude=float(c[1]))

Placemark = namedtuple("Placemark", ["name", "type", "folders", "coordinates"])


class KMLReader:
    def __init__(self, *args, **kwargs) -> None:
        # file name of kml
        kml_file = kwargs["file"]

        # reading kml file with standard python xml library.
        # because "*.kml" files have the structure simmilar to the xml so we are parsing it through xml and creating a tree
        self.tree = ET.parse(kml_file)

        # get the root elemtent of the tree
        self.root = self.tree.getroot()

        # get all the namespace present in the file, this expect direct path to xml/kml file
        self.namespaces = self.get_namespaces(kml_file)

        # by default '' namespace is used,  "{"  "}" should be around the namespace -> because we are concatenating them as strings in adjust_namespace method
        self.namespace = f"{{{self.namespaces['']}}}"

        # geometries we are interested in, LineString for Path
        self.geometries = ["Point", "LineString", "Polygon"]

        # exracting all the data from kml from "Document" Node
        document = self.findfirst_from_parent(c_elem="Document")

        # IMPORTANT: we import the KMLReader module one and which initliaze all the fucntions attached to it, later on when we pass more and more file then this
        # it also keep the records from old files because of function definitions are freezed and same passed args are being used so, we have to
        # explicitly pass the empty string for every new file.
        self.data = self.get_data(element=document, to_visit=[], data=[], dir_history=[])

    # =========================== DATA ===========================

    def get_data(self, element, to_visit=[], data=[], dir_history=[]):
        """
        this is a recursive function, which consider take record of two things
        1 - "data" : data extracted from each placemark node present in the folder
        2 - "to_visit" : folders to visis
        """

        # this will get the parent elemetn name (except document case it will use to get folder names)
        name = self.get_element_name(element)
        # to keep track of the all parent folders for each node we are visting.
        dir_history.append(name)

        # how many direct placemarks are under the element (folder or document)
        placemarks = self.findall_direct_decendents(p_elem=element, c_elem="Placemark")

        # move on each placemark, and append data in data[] array
        for p_elem in placemarks:
            data.extend(self.parse_placemark(element=p_elem, dir_chain=dir_history))

        # if further folders found append them to to_visit list for in future processing
        folders_tovisit = self.findall_direct_decendents(p_elem=element, c_elem="Folder")

        # same as above folder nodes, but zipped with parent name history which is requried.
        folders_tovisit = [(f, dir_history.copy()) for f in folders_tovisit]

        # appending to list, for future proicessing
        to_visit.extend(folders_tovisit)

        if to_visit:
            # f_elem: Folder element in the kml || name_chain: hierarchy of folders
            f_elem, dir_chain = to_visit.pop()
            self.get_data(element=f_elem, to_visit=to_visit, data=data, dir_history=dir_chain)

        return data

    def parse_placemark(self, element, dir_chain=[]):
        element_name = self.get_element_name(element)

        # to hold multiple geometries in a single placemark element
        geometries_data = []

        # g => self.geometries => ["Polygon", "Point", "LineString"]
        for g in self.geometries:
            # get all the geometries of "g" type from placemark element
            g_elems = self.findall_from_parent(p_elem=element, c_elem=g)

            # if a placemark has multiple "g" elements
            for g_elem in g_elems:
                # get coordinates of that geometry present in the placemark, some polygon can have multiple coordinatesm because of Holes in them.
                coords_elem = self.findfirst_from_parent(p_elem=g_elem, c_elem="coordinates")

                try:
                    # get the str representation of that coords element present in the placemark node
                    str_coords = [single_coords for single_coords in coords_elem.text.strip().split(" ")]
                    float_coords = [to_coordinates(str_coord.split(",")) for str_coord in re.findall(r"\S+", coords_elem.text)]
                except AttributeError as ae:
                    print(f"\n{type(ae)} has occurred in {g} type,\nDirectory Chain: {' => '.join(dir_chain)},\nNo Values in <coordinates> node.")
                    print(f"Coordiantes: {coords_elem}\n")
                    continue
                except ValueError as ve:
                    print(
                        f"\n{type(ve)} has occurred in {g} type,\nDirectory Chain: {' => '.join(dir_chain)},\nAmbiguous Values in <coordinates> node."
                    )
                    print(f"Coordiantes: {str_coords}\n")
                    continue

                geometries_data.append(Placemark(name=element_name, type=g, folders=dir_chain, coordinates=float_coords))

        return geometries_data

    def get_element_name(self, element):
        try:
            # this will return the text present in the name node present in the element
            element_name = self.findfirst_direct_decendent(p_elem=element, c_elem="name").text.strip()
        except AttributeError as ae:
            # if no <name> node is not present in the kml for that specific element, we will consider it empty and will return empty string
            element_name = ""

        return element_name

    # ======================== ELEMENTS SEARCH ========================

    def findall_from_parent(self, p_elem=None, c_elem=None):
        # if no parent is provided then use root as parent
        _parent = p_elem if p_elem != None else self.root

        # concatenating the namespace with the element name, because it is necessary
        _child = self.adjust_namespace(c_elem)

        return _parent.findall(f".//{_child}")

    def findfirst_from_parent(self, p_elem=None, c_elem=None):
        # if no parent is provided then use root as parent
        _parent = p_elem if p_elem != None else self.root

        # concatenating the namespace with the element name, because it is necessary
        _child = self.adjust_namespace(c_elem)

        # child elements we are interested in from specfic parent node
        _elems = _parent.findall(f".//{_child}")

        # if element exist then return the first else None
        return _elems[0] if _elems else None

    def findall_direct_decendents(self, p_elem=None, c_elem=None):
        # if no parent is provided then use root as parent
        _parent = p_elem if p_elem != None else self.root

        # concatenating the namespace with the element name, because it is necessary
        _child = self.adjust_namespace(c_elem)

        return _parent.findall(f"./{_child}")

    def findfirst_direct_decendent(self, p_elem=None, c_elem=None):
        # if no parent is provided then use root as parent
        _parent = p_elem if p_elem != None else self.root

        # concatenating the namespace with the element name, because it is necessary
        _child = self.adjust_namespace(c_elem)

        # find all the direct element of type child in parent
        _elems = _parent.findall(f"./{_child}")

        # if element exist then return the first else None
        return _elems[0] if _elems else None

    # =========================== NAMESPACE ===========================

    def get_namespaces(self, kml_file):
        namespaces = dict([node for _, node in ET.iterparse(kml_file, events=["start-ns"])])
        return namespaces

    def adjust_namespace(self, element):
        if hasattr(element, "tag"):
            return element.tag
        if isinstance(element, str):
            m = re.match(r"\{.*\}", element)
            return element if m else f"{self.namespace}{element}"

    def get_namespace(self, element):
        if hasattr(element, "tag"):
            m = re.match(r"\{.*\}", element.tag)
            return m.group(0) if m else ""
        else:
            m = re.match(r"\{.*\}", element)
            return m.group(0) if m else ""

    def add_namespace(self, element):
        elem_name = f"{self.namespace}{element}"
        return elem_name

    def remove_namespace(self, element):
        elem_name = element.replace(f"{self.namespace}", "")
        return elem_name
