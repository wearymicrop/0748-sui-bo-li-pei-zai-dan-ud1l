from app.quality import token

COLORS = {
    "白": "白料",
    "透明": "白料",
    "白料": "白料",
    "绿": "绿料",
    "绿料": "绿料",
    "棕": "棕料",
    "棕料": "棕料",
}
GRADES = {"A", "B", "C"}


def normalize_color(value):
    return COLORS[token(value)]


def grade_for(offcolor, impurity):
    if offcolor <= 30000 and impurity <= 10000:
        return "A"
    if offcolor <= 100000 and impurity <= 30000:
        return "B"
    return "C"
