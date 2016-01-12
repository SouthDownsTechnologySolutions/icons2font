#!/usr/bin/env python2.7

import argparse
import logging
import md5
import os
import sys

from xml.dom import minidom

import fontforge

log = logging.getLogger(__name__)

DESIGNER_FONT_START_CHAR = "A"
GSIZE = 1400

HEADER = """<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" >
<svg xmlns="http://www.w3.org/2000/svg">
<metadata></metadata>
<defs>
<font id="{}">
<font-face units-per-em="2048" ascent="1536" descent="-512" />
<missing-glyph horiz-adv-x="512" />
<glyph horiz-adv-x="0" />
<glyph horiz-adv-x="0" />
"""

GLYPH = """<glyph unicode="{0}" horiz-adv-x="1400" d="{1}" />\n\n"""

FOOTER = """

</font>
</defs>
</svg>
"""

DOC_HEADER = """
<!DOCTYPE html>
<!--[if lt IE 7 ]><html class="ie ie6" lang="en"> <![endif]-->
<!--[if IE 7 ]><html class="ie ie7" lang="en"> <![endif]-->
<!--[if IE 8 ]><html class="ie ie8" lang="en"> <![endif]-->
<!--[if (gte IE 9)|!(IE)]><!--><html lang="en"> <!--<![endif]-->
<head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="{0}.css">
    <style type="text/css">
body {{
 font-size: 3em;
 color: black;
}}

/* designer font */
@font-face {{
  font-family: "{0}-designer";
  src: url('{0}-designer.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
  font-feature-settings: "calt=0,liga=0"
}}
textarea {{
 font-family: {0}-designer;
 font-size: 3em;
 width: 100%;
 height: 300px;
}}
    </style>
</head>
<body>
<h1>Font: {0}</h1>
"""
DOC_FOOTER = """
<hr>
try out and <a href='{0}-designer.ttf'>download</a> desinger font
<textarea>a b c d</textarea>
</body>
</html>
"""

#  src: url('{0}.eot');
#  src: url('{0}.eot#iefix') format('embedded-opentype'),
#       url('{0}.ttf') format('truetype'),
#       url('{0}.woff') format('woff'),
#       url('{0}.svg') format('svg'),
#       url('{0}.otf') format("opentype");


CSS_HEADER = """@font-face {{
  font-family: "{0}";
  src: url('{0}.eot?h={1}');
  src: url('{0}.eot?h={1}#iefix') format('embedded-opentype'),
       url('{0}.ttf?h={1}') format('truetype'),
       url('{0}.woff?h={1}') format('woff'),
       url('{0}.svg?h={1}') format('svg'),
       url('{0}.otf?h={1}') format("opentype");
  font-weight: normal;
  font-style: normal;
  font-feature-settings: "calt=0,liga=0"
}}
[class^="{0}-"], [class*=" {0}-"] {{
  font-family: {0};
  font-weight: normal;
  font-style: normal;
  display: inline-block;
  text-decoration: inherit;
  vertical-align: baseline;
  -webkit-font-smoothing: antialiased;
}}
"""

USER_AREA = 0xf000

COMMANDS_ABS = "MZLHVCSQTA"
COMMANDS_REL = COMMANDS_ABS.lower()
COMMANDS = COMMANDS_ABS + COMMANDS_REL

def between(a, b, s):
    first = s.find(a)
    first += len(a)
    last = s.find(b, first)
    return s[first:last]

def htmlhex(n):
    return hex(n).replace("0x","&#x") + ";"

def svg_paths(svg):
    xmldoc = minidom.parseString(svg)
    paths = []

    # view box
    for s in xmldoc.getElementsByTagName('svg'):
        try:
            viewBox = map(float, s.attributes['viewBox'].value.split())
        except:

            viewBox = [0,0,
                float(s.attributes['width'].value),
                float(s.attributes['height'].value)]
    #    width="100" height="100"

    for s in xmldoc.getElementsByTagName('path'):
        d = s.attributes['d'].value
        paths.append(d)


    for s in xmldoc.getElementsByTagName('polygon'):
        d = s.attributes['points'].value
        paths.append("M"+d)

    for s in xmldoc.getElementsByTagName('rect'):
        try: x = float(s.attributes['x'].value)
        except: x = 0
        try: y = float(s.attributes['y'].value)
        except: y = 0

        w = float(s.attributes['width'].value)
        h = float(s.attributes['height'].value)
        p = ["M",x,y, x+w,y, x+w,y+h, x,y+h, x,y, "Z"]
        paths.append(" ".join(map(str,p)))

    for s in xmldoc.getElementsByTagName('circle'):
        cx = float(s.attributes['cx'].value)
        cy = float(s.attributes['cy'].value)
        r = float(s.attributes['r'].value)
        p =["M", cx-r, cy,
            "a", r,r,  0,  1,0,  (r*2),0,
            "a", r,r,  0,  1,0,  -(r*2),0,
            "Z"]
        paths.append(" ".join(map(str,p)))

        x = cx-r
        y = cy-r
        w = 2*r
        h = 2*r

        p = ["M",x,y, x+w,y, x+w,y+h, x,y+h, x,y, "Z"]
        #paths.append(" ".join(map(str,p)))


    return viewBox, paths

def parse_path(path):
    commands = []
    command = []
    word = []
    for c in path:
        if c in COMMANDS:
            if word:
                command.append(float("".join(word)))
                word = []
            if command:
                commands.append(command)
            command = [c]
        elif c in " ,":
            if word:
                command.append(float("".join(word)))
                word = []
        elif c in "+-":
            if word:
                command.append(float("".join(word)))
                word = []
            word.append(c)
        else:
            word.append(c)
    if word:
        command.append(float("".join(word)))
        word = []
    if command:
        commands.append(command)
    return commands

def compile_path(commands):
    buf = []
    for command in commands:
        buf.append(command[0])
        for n in command[1:]:
            buf.append(str(n))
    return " ".join(buf)


def do_glyph(data, glyphname, svg, scale=1.0, translate_y=0.0):
    """ converts a file into a svg glyph """

    local_gsize = GSIZE * scale

    viewBox, paths = svg_paths(data)
    # font needs to be of one path
    path = " ".join(paths)
    commands = parse_path(path)

    tranx, trany, sizex, sizey = viewBox
    tranx = -tranx
    trany = -trany

    size = max(sizex, sizey)
    scale = local_gsize/size

    if size - sizey > 0:
        trany += (size - sizey)/2
    if size - sizex > 0:
        tranx += (size - sizex)/2

    trany += translate_y

    #print "translate", tranx, trany, "scale", scale

    prev_op = None
    for command in commands:
        op = command[0]

        if op in "Aa":
            # arcs require special fancy scaling
            command[1] *= scale
            command[2] *= scale
            # presurve flags
            command[4] = int(command[4])
            command[5] = int(command[5])
            # scale the radii
            command[6] *= scale
            command[7] *= scale
        else:
            for i,num in enumerate(command):
                if num == op: continue
                if op in COMMANDS_ABS:
                    if op == "H":
                        command[i] *= scale
                        command[i] += tranx * scale
                    elif op == "V":
                        command[i] *= -scale
                        command[i] += -trany * scale + local_gsize
                    else:
                        if i % 2 == 1:
                            command[i] *= scale
                            command[i] += tranx * scale
                        else:
                            command[i] *= -scale
                            command[i] += -trany * scale + local_gsize
                else:
                    if op in "h":
                        command[i] *= scale
                    elif op in "v":
                        command[i] *= -scale
                    else:
                        if i % 2 == 1:
                            command[i] *= scale
                        else:
                            command[i] *= -scale
        # special case for first relative m (its just like abs M)
        if op == "m" and prev_op == None:
            command[1] += tranx * scale
            command[2] += -trany * scale + local_gsize
        prev_op = op

    #commands.insert(0, ['M', tranx*scale, -trany*scale])

    path = compile_path(commands)
    #print "final path", path
    svg.write(GLYPH.format(glyphname, path))


    #svg.write(GLYPH.format(glyphname, path))

def gen_svg_font(
        glyph_files, output_path, font_name, glyph_name,
        scale=1.0, translate_y=0.0,
        scale_overrides=None, translate_y_overrides=None):
    scale_overrides = scale_overrides or {}
    translate_y_overrides = translate_y_overrides or {}

    svg = open(output_path, 'w')
    svg.write(HEADER.format(font_name))

    # use the special unicode user area for char encoding
    index = 0
    #current = ord("a")
    for f in glyph_files:
        glyph_friendly_name = os.path.splitext(os.path.split(f)[1])[0]
        data = open(f).read()

        glyph_scale = scale
        if glyph_friendly_name in scale_overrides:
            glyph_scale = scale_overrides[glyph_friendly_name]
        log.debug("Using scale {}={}".format(glyph_friendly_name, glyph_scale))

        glyph_translate_y = translate_y
        if glyph_friendly_name in translate_y_overrides:
            glyph_translate_y = translate_y_overrides[glyph_friendly_name]
        log.debug("Using translate Y {}={}".format(glyph_friendly_name, glyph_translate_y))

        do_glyph(data, glyph_name(index), svg, scale=glyph_scale, translate_y=glyph_translate_y)

        index += 1

    svg.write(FOOTER)
    svg.flush()
    svg.close()

    log.info("Generated {}".format(output_path))


def gen_scss_for_font(glyph_files, output_path, font_name, hash):
    scss = open(output_path, 'w')
    scss.write(CSS_HEADER.format(font_name, hash))

    for index, f in enumerate(glyph_files):
        glyph_name = font_name + "-" + f.split("/")[-1].replace(".svg", "")
        scss.write(
            '.{0}:before {{\n    content: "\{1:04x}";\n}}\n'.format(
                glyph_name,
                USER_AREA + index))

    log.info("Generated {}".format(output_path))


def gen_html_for_font(glyph_files, output_path, font_name):
    doc = open(output_path,'w')
    doc.write(DOC_HEADER.format(font_name))

    for index, f in enumerate(glyph_files):
        glyph_name = font_name + "-" + f.split("/")[-1].replace(".svg", "")
        art_name = chr(ord(DESIGNER_FONT_START_CHAR) + index)
        doc.write("<i class='{0}'></i> {0} ({1}) <br/>\n".format(
            glyph_name, art_name))

    doc.write(DOC_FOOTER.format(font_name))

    log.info("Generated {}".format(output_path))


def parse_args():
    """
    All of the boolean options have both an 'on' and an 'off' argument, which
    defaults to 'on'. The only reason to have 'on' at all is so that you can
    be very explicit about what you want, without worrying about whether the
    defaults will change or whether you'll need to override it later.
    """

    parser = argparse.ArgumentParser(
        description='Convert a folder of SVG files into several font formats')
    parser.add_argument(
        "input_dir", action="store", help="Path to a folder of SVG files")
    parser.add_argument(
        "output_dir", action="store", help="Path to a folder to put output files in")
    parser.add_argument(
        "font_name", default="icon", action="store", help="Output file name *and* font name. Defaults to 'icon'.")

    parser.add_argument('-v', '--verbose', action='count', help="Add one for info logging, add another for debug logging")

    parser.add_argument('--designer', action='store_true', default=True, help='(default) Generate "designer" variant (uses ASCII range instead of user extension range)')
    parser.add_argument('--no-designer', action='store_false', dest='designer', help="Don't generate \"designer\" variant")

    parser.add_argument('--ignore', action='append', default=[], help="Ignore a glyph. Do not include the .svg extension. Can be used more than once.")

    transforms_group = parser.add_argument_group("Transforms", "Translate and scale glyphs")

    transforms_group.add_argument("--scale-all", default=1, action='store', type=float, help="Amount by which to scale all glyphs")
    transforms_group.add_argument("--translate-y-all", default=0, action='store', type=float, help="Amount by which to offset all glyphs on the Y axis. What are the units? That's for you to find out.")

    transforms_group.add_argument(
        "--scale-one", nargs=2, metavar=('GLYPH_NAME', 'AMOUNT'), action='append', default=[],
        help="'--scale-one airplane 2' would scale the 'airplane' glyph 2x. Can be used more than once. This will _replace_ the global scale value for this glyph.")
    transforms_group.add_argument(
        "--translate-y-one", nargs=2, metavar=('GLYPH_NAME', 'AMOUNT'), action='append', default=[],
        help="'--translate-y-one airplane 5' would move the 'airplane' glyph down 5 units. Can be used more than once. This will _replace_ the global translate-y value for this glyph.")

    formats_group = parser.add_argument_group('Formats', 'Enable or disable individual formats. All are enabled by default.')

    for fmt in ('scss', 'html', 'woff', 'otf', 'eot'):
        formats_group.add_argument('--' + fmt, action='store_true', default=True, help='Generate {} files for fonts'.format(fmt.upper()))
        formats_group.add_argument('--no-' + fmt, action='store_false', dest=fmt, help="Don't generate {} files for fonts".format(fmt.upper()))

    return parser.parse_args()


def configure_logging(level=0):
    log_level = logging.WARNING
    if level == 1:
        log_level = logging.INFO
    elif level > 1:
        log_level = logging.DEBUG
    logging.basicConfig(format='%(message)s', level=log_level)


def get_glyph_file_paths(input_dir, ignore):
    ignore = set(ignore)
    glyph_files = []
    for f in sorted(os.listdir(input_dir)):
        if not f.endswith(".svg"):
            continue
        glyph_name = os.path.splitext(f)[0]
        if glyph_name in ignore:
            log.info("Ignoring glyph {}".format(glyph_name))
            continue
        path = os.path.join(input_dir, f)
        glyph_files.append(path)
        log.debug("Including file {}".format(path))
    return glyph_files


def main():
    args = parse_args()
    configure_logging(args.verbose)

    scale_overrides = {name: float(amt) for (name, amt) in args.scale_one}
    translate_y_overrides = {name: float(amt) for (name, amt) in args.translate_y_one}

    log.info("Scale overrides: {}".format(scale_overrides))
    log.info("Translate Y overrides: {}".format(translate_y_overrides))

    designer_font_name = args.font_name + '-designer'

    # make sure output dir exists
    try:
       os.makedirs(args.output_dir)
    except OSError:
       pass

    glyph_files = get_glyph_file_paths(args.input_dir, args.ignore)

    # generate browser svg font
    gen_svg_font(
        glyph_files,
        os.path.join(args.output_dir, args.font_name + '.svg'),
        args.font_name,
        glyph_name=lambda i:htmlhex(i + USER_AREA),
        scale=args.scale_all,
        translate_y=args.translate_y_all,
        scale_overrides=scale_overrides,
        translate_y_overrides=translate_y_overrides
    )

    if args.scss:
        # get file hash
        svg_font_hash = md5.new(open(os.path.join(args.output_dir, args.font_name+".svg")).read()).hexdigest()[:5]

        # generate scss
        gen_scss_for_font(
            glyph_files,
            os.path.join(args.output_dir, args.font_name + ".scss"),
            args.font_name,
            svg_font_hash
        )

    if args.html:
        # generate sample html
        gen_html_for_font(
            glyph_files,
            os.path.join(args.output_dir, args.font_name + ".html"),
            args.font_name
        )

    # make ttf, woff, off, and eot browser fonts
    font = fontforge.open(os.path.join(args.output_dir, args.font_name + ".svg"))

    ttf_path = os.path.join(args.output_dir, args.font_name + ".ttf")
    font.generate(ttf_path)
    log.info("Generated {}".format(ttf_path))

    if args.woff:
        path = os.path.join(args.output_dir, args.font_name + ".woff")
        font.generate(path)
        log.info("Generated {}".format(path))
    if args.otf:
        path = os.path.join(args.output_dir, args.font_name + ".otf")
        font.generate(path)
        log.info("Generated {}".format(path))
    if args.eot:
        eot_path = os.path.join(args.output_dir, args.font_name + '.eot')
        os.system("ttf2eot {0} > {1}".format(ttf_path, eot_path))
        log.info("Generated {}".format(eot_path))

    if args.designer:
        gen_svg_font(
            glyph_files,
            os.path.join(args.output_dir, designer_font_name + '.svg'),
            designer_font_name,
            glyph_name=lambda i:htmlhex(i+ord(DESIGNER_FONT_START_CHAR)),
            scale=args.scale_all,
            translate_y=args.translate_y_all,
            scale_overrides=scale_overrides,
            translate_y_overrides=translate_y_overrides
        )

        font = fontforge.open(os.path.join(args.output_dir, designer_font_name + ".svg"))
        path = os.path.join(args.output_dir, designer_font_name + ".ttf")
        font.generate(path)
        log.info("Generated {}".format(path))


if __name__ == "__main__":
    main()
