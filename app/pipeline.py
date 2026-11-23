from app.modules.m1_weighing.service import weigh
from app.modules.m2_moisture.service import water_samples
from app.modules.m3_grading.service import grade_lots
from app.modules.m4_drymass.service import fold
from app.modules.m5_loading.service import load
from app.modules.m6_reconcile.service import reconcile


def calculate(data):
    weighing = weigh(data)
    lots = weighing["lots"]
    moisture = water_samples(data, lots)
    grading = grade_lots(data, lots)
    drymass = fold(lots, moisture)
    loading = load(data, drymass, grading)
    return {
        "weighing": weighing,
        "moisture": moisture,
        "grading": grading,
        "drymass": drymass,
        "loading": loading,
        "reconcile": reconcile(weighing, drymass, loading),
    }
