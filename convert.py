import ezdxf
from svg.path import parse_path
from xml.dom import minidom
import webbrowser
from uuid import uuid4


class Svg2DxfConverter:
    def __init__(self, svg_path: str) -> None:
        self.dxf = ezdxf.new("R2010")
        self.msp = self.dxf.modelspace()
        self.svg = minidom.parse(svg_path)
        self.dxf_path = ""

    def convert_lines(self):
        for line_svg in self.svg.getElementsByTagName("line"):
            self.msp.add_polyline2d(
                [
                    (
                        float(line_svg.getAttribute("x1")),
                        float(line_svg.getAttribute("y1")),
                    ),
                    (
                        float(line_svg.getAttribute("x2")),
                        float(line_svg.getAttribute("y2")),
                    ),
                ]
            )

    def create_layer_or_get_if_already_exists(self, layer_name):
        return (
            self.dxf.layers.get(layer_name)
            if layer_name in self.dxf.layers
            else self.dxf.layers.new(layer_name)
        )

    def convert_texts(self):
        for ifc_element_svg in self.svg.getElementsByTagName("text"):
            class_svg = ifc_element_svg.getAttribute("class")
            if class_svg:
                continue
            transform = ifc_element_svg.getAttribute("transform")
            x = float(transform.split("(")[1].split(",")[0])
            y = float(transform.split(",")[1].split(")")[0])

            for child in ifc_element_svg.childNodes:
                if child.localName == "tspan":
                    text = child.firstChild.nodeValue

                    text_dxf = self.msp.add_text(text=text)
                    text_dxf.translate(x, -y, 0)

    def convert_paths(self):
        for ifc_element_svg in self.svg.getElementsByTagName("g"):
            class_svg = ifc_element_svg.getAttribute("class")
            if not ifc_element_svg.hasAttribute("ifc:guid") and "cut" not in class_svg:
                continue
            layer_name = class_svg
            layer_name_split = layer_name.split(" ")
            layer_name = ""
            for elt in layer_name_split:
                if elt.startswith("Ifc"):
                    layer_name += elt
            for elt in layer_name_split:
                if elt == "cut":
                    layer_name += "_cut"
            paths = ifc_element_svg.getElementsByTagName("path")[:]
            paths_parsed = [parse_path(path.getAttribute("d")) for path in paths]
            if all(len(path_parsed) == 2 for path_parsed in paths_parsed):
                first_line = paths_parsed[0][1]
                first_coord = [first_line.start.real, -first_line.start.imag, 0]
                block_def = self.dxf.blocks.new(
                    name=ifc_element_svg.getAttribute("ifc:guid") + str(uuid4())
                )
                for path_parsed in paths_parsed:
                    line = path_parsed[1]
                    polyline_coords = [
                        (
                            line.start.real - first_coord[0],
                            -line.start.imag - first_coord[1],
                        ),
                        (
                            line.end.real - first_coord[0],
                            -line.end.imag - first_coord[1],
                        ),
                    ]
                    p = block_def.add_polyline2d(
                        polyline_coords,
                        dxfattribs={"layer": 0},
                    )
                self.msp.add_blockref(
                    name=block_def.name,
                    insert=first_coord,
                    dxfattribs={"layer": layer_name},
                )
            else:  # Hatch
                polyline_coords = []
                for line in paths_parsed[0][1::]:
                    x2, y2 = line.end.real, line.end.imag
                    if polyline_coords:
                        polyline_coords.append((x2, -y2))
                        continue
                    x1, y1 = line.start.real, line.start.imag
                    polyline_coords = [(x1, -y1), (x2, -y2)]
                hatch = self.msp.add_hatch(
                    color=256,  # 256 = BYLAYER
                    dxfattribs={"layer": layer_name},
                )
                hatch.paths.add_polyline_path(polyline_coords)

                first_coord = [polyline_coords[0][0], -polyline_coords[0][1], 0]
                block_def = self.dxf.blocks.new(
                    name=(ifc_element_svg.getAttribute("ifc:guid") or str(uuid4()))
                    + "_cut"
                )
                polyline = block_def.add_polyline2d(
                    polyline_coords,
                    dxfattribs={"layer": 0},
                    close=True,
                )
                polyline.translate(-first_coord[0], -first_coord[1], 0)
                self.msp.add_blockref(
                    name=block_def.name,
                    insert=first_coord,
                    dxfattribs={
                        "layer": layer_name,
                        "color": 0,  # 0 = BYBLOCK
                    },
                )

    def save(self, dxf_path):
        self.svg.unlink()
        self.dxf.saveas(dxf_path)
        self.dxf_path = dxf_path

    def open_dxf(self):
        if self.dxf_path:
            webbrowser.open(self.dxf_path)


if __name__ == "__main__":
    converter = Svg2DxfConverter("test.svg")
    converter.convert_paths()
    converter.convert_texts()
    converter.save("test.dxf")
    if converter.dxf_path:
        webbrowser.open(converter.dxf_path)
