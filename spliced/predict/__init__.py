from .abi_laboratory import AbiLaboratoryPrediction
from .base import Prediction
from .libabigail import LibabigailPrediction
from .smeagle import SmeaglePrediction
from .spack import SpackTest
from .symbols import SymbolsPrediction


def get_predictors(names=None):
    """
    Get a lookup of predictors for an experiment to run.
    """
    names = names or []
    predictors = {
        "smeagle": SmeaglePrediction(),
        "symbols": SymbolsPrediction(),
        "libabigail": LibabigailPrediction(),
        "spack-test": SpackTest(),
        "abi-laboratory": AbiLaboratoryPrediction(),
    }
    if names:
        keepers = {}
        for name, predictor in predictors.items():
            if name in names:
                keepers[name] = predictor
        predictors = keepers

    return predictors
