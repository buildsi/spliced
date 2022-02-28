from .base import Prediction, Actual
from .symbolator import SymbolatorPrediction
from .libabigail import LibabigailPrediction
from .spack import SpackTest


def get_predictors(names=None):
    """
    Get a lookup of predictors for an experiment to run.
    """
    names = names or []
    predictors = {
        "symbolator": SymbolatorPrediction(),
        "libabigail": LibabigailPrediction(),
        "spack-test": SpackTest(),
    }
    if names:
        keepers = {}
        for name, predictor in predictors.items():
            if name in names:
                keepers[name] = predictor
        predictors = keepers

    # Provide the actual no matter what
    predictors["actual"] = Actual()

    return predictors
