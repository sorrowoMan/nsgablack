from nsgablack.adapters.cmaes import CMAESAdapter, CMAParameters, GaussianCohortSampler


def build_adapter(settings):
    scalar = settings.fixture == "scalar"
    fixed = ([[[-1.], [0.], [1.], [2.]]] if scalar else
             [[[ -1., 0.], [0., 1.], [1., 0.], [0., -1.]]] if settings.fixture == "matrix" else ())
    parameters = (CMAParameters(weights=(.5, .5), cc=.5, cs=.5, c1=.25, cmu=.25, damping=1.)
                  if scalar else CMAParameters())
    return CMAESAdapter([0.] if scalar else [0., 0.], sigma=1. if scalar else .5,
        parameters=parameters, sampler=GaussianCohortSampler(settings.seed, fixed_batches=fixed))
