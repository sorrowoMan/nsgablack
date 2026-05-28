"""GMM: black-box negative log-likelihood problem."""
import numpy as np
from nsgablack.core.base import BlackBoxProblem


class GMMProblem(BlackBoxProblem):
    def __init__(self, data, k=3):
        self._data = np.asarray(data, dtype=float)
        self._n_samples, self._n_features = self._data.shape
        self._k = int(k)
        self._dim = self._k * self._n_features * 3

        data_min = self._data.min(axis=0)
        data_max = self._data.max(axis=0)
        pad = (data_max - data_min) * 0.5
        mean_low = data_min - pad
        mean_high = data_max + pad
        sigma_low = np.full(self._n_features, 0.1)
        sigma_high = np.full(self._n_features, 5.0)

        import itertools
        mean_bounds = list(itertools.chain.from_iterable(
            [(float(mean_low[j]), float(mean_high[j])) for j in range(self._n_features)]
            for _ in range(self._k)
        ))
        sigma_bounds = list(itertools.chain.from_iterable(
            [(float(sigma_low[j]), float(sigma_high[j])) for j in range(self._n_features)]
            for _ in range(self._k)
        ))
        pi_bounds = [(-10.0, 10.0)] * (self._k * self._n_features)

        all_bounds = mean_bounds + sigma_bounds + pi_bounds
        super().__init__(dimension=self._dim, objectives=["minimize"],
                         bounds=all_bounds, name="gmm_nll")

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float).ravel()
        nf = self._n_features
        k = self._k
        d = self._data

        m_end = k * nf
        s_end = 2 * k * nf

        means = arr[:m_end].reshape(k, nf)
        sigmas = np.clip(arr[m_end:s_end].reshape(k, nf), 0.01, None)
        pi_logits = arr[s_end:s_end + k]
        pi_logits = pi_logits - pi_logits.max()
        pis = np.exp(pi_logits)
        pis = pis / pis.sum()

        log_prob = np.empty((self._n_samples, k), dtype=float)
        for c in range(k):
            diff = d - means[c]
            inv_s2 = 1.0 / (sigmas[c] ** 2)
            log_det = np.sum(np.log(sigmas[c]))
            quad = np.sum(diff * diff * inv_s2, axis=1)
            log_prob[:, c] = -0.5 * (nf * np.log(2 * np.pi) + 2 * log_det + quad)

        log_prob += np.log(pis + 1e-300)
        max_log = log_prob.max(axis=1, keepdims=True)
        log_sum = max_log.ravel() + np.log(np.sum(np.exp(log_prob - max_log), axis=1) + 1e-300)
        nll = -float(np.sum(log_sum))
        if not np.isfinite(nll):
            return 1e12
        return nll
