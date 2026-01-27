import numpy as np
from typing import Callable, List, Dict, Tuple, Any
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA, KernelPCA
from sklearn.cross_decomposition import PLSRegression
from sklearn.linear_model import Ridge


class PCAReducer:
    """基于 PCA 的线性降维"""

    def __init__(self, n_components: int, scale: bool = True):
        self.n_components = n_components
        self.scale = scale
        self.scaler = StandardScaler() if scale else None
        self.pca = PCA(n_components=n_components, random_state=42)
        self.fitted_ = False
        self.bounds_ = None

    def fit(self, X: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        X_proc = X
        if self.scaler is not None:
            X_proc = self.scaler.fit_transform(X_proc)
        self.pca.fit(X_proc)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, "PCAReducer 未拟合"
        X_proc = X
        if self.scaler is not None:
            X_proc = self.scaler.transform(X_proc)
        return self.pca.transform(X_proc)

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, "PCAReducer 未拟合"
        X_proc = self.pca.inverse_transform(Z)
        if self.scaler is not None:
            X = self.scaler.inverse_transform(X_proc)
        else:
            X = X_proc
        X_clipped = np.empty_like(X)
        for i, (low, high) in enumerate(self.bounds_):
            X_clipped[:, i] = np.clip(X[:, i], low, high)
        return X_clipped


class KernelPCAReducer:
    """基于 Kernel PCA 的非线性降维"""

    def __init__(self, n_components: int, kernel: str = 'rbf', scale: bool = True, **kernel_kwargs):
        self.n_components = n_components
        self.kernel = kernel
        self.kernel_kwargs = kernel_kwargs
        self.scale = scale
        self.scaler = StandardScaler() if scale else None
        self.kpca = KernelPCA(n_components=n_components, kernel=kernel, fit_inverse_transform=False, **kernel_kwargs)
        self.decoder = Ridge(alpha=1.0)
        self.fitted_ = False
        self.bounds_ = None

    def fit(self, X: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.fit_transform(Xp)
        Z = self.kpca.fit_transform(Xp)
        self.decoder.fit(Z, X)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'KernelPCAReducer 未拟合'
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.transform(Xp)
        return self.kpca.transform(Xp)

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'KernelPCAReducer 未拟合'
        X_hat = self.decoder.predict(Z)
        Xc = np.empty_like(X_hat)
        for i, (low, high) in enumerate(self.bounds_):
            Xc[:, i] = np.clip(X_hat[:, i], low, high)
        return Xc


class PLSReducer:
    """PLS 监督式线性降维"""

    def __init__(self, n_components: int, scale: bool = True):
        self.n_components = n_components
        self.scale = scale
        self.x_scaler = StandardScaler() if scale else None
        self.pls = PLSRegression(n_components=n_components)
        self.x_mean_ = None
        self.fitted_ = False
        self.bounds_ = None

    def fit(self, X: np.ndarray, y: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        Xp = X
        if self.x_scaler is not None:
            Xp = self.x_scaler.fit_transform(Xp)
        self.pls.fit(Xp, y.reshape(-1, 1))
        self.x_mean_ = np.mean(X, axis=0)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'PLSReducer 未拟合'
        Xp = X
        if self.x_scaler is not None:
            Xp = self.x_scaler.transform(Xp)
        T = self.pls.transform(Xp)
        return T

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'PLSReducer 未拟合'
        P = self.pls.x_loadings_
        X_hat = Z @ P.T
        if self.x_scaler is not None:
            X_hat = X_hat + self.x_scaler.mean_
        else:
            X_hat = X_hat + self.x_mean_
        Xc = np.empty_like(X_hat)
        for i, (low, high) in enumerate(self.bounds_):
            Xc[:, i] = np.clip(X_hat[:, i], low, high)
        return Xc


class AutoencoderReducer:
    """基于 Keras 的 MLP 自编码器"""

    def __init__(self, n_components: int, hidden_ratio: float = 2.0, scale: bool = True,
                 epochs: int = 100, batch_size: int = 64, learning_rate: float = 1e-3):
        self.n_components = n_components
        self.hidden_ratio = hidden_ratio
        self.scale = scale
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.scaler = StandardScaler() if scale else None
        self.model = None
        self.encoder = None
        self.decoder = None
        self.fitted_ = False
        self.bounds_ = None

    def _build(self, input_dim):
        try:
            import tensorflow as tf
            keras = tf.keras
            layers = tf.keras.layers
        except Exception as e:
            raise ImportError(f"需要 tensorflow 才能使用 AutoencoderReducer: {e}")
        inputs = keras.Input(shape=(input_dim,))
        h = layers.Dense(int(self.hidden_ratio * self.n_components), activation='relu')(inputs)
        z = layers.Dense(self.n_components, activation=None, name='latent')(h)
        h2 = layers.Dense(int(self.hidden_ratio * self.n_components), activation='relu')(z)
        outputs = layers.Dense(input_dim, activation=None)(h2)
        model = keras.Model(inputs, outputs)
        model.compile(optimizer=keras.optimizers.Adam(self.learning_rate), loss='mse')

        encoder = keras.Model(inputs, z)
        latent_inputs = keras.Input(shape=(self.n_components,))
        d = model.layers[-2](latent_inputs)
        decoded = model.layers[-1](d)
        decoder = keras.Model(latent_inputs, decoded)
        return model, encoder, decoder

    def fit(self, X: np.ndarray, bounds: List[Tuple]):
        self.bounds_ = bounds
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.fit_transform(Xp)
        self.model, self.encoder, self.decoder = self._build(Xp.shape[1])
        self.model.fit(Xp, Xp, epochs=self.epochs, batch_size=self.batch_size, verbose=0)
        self.fitted_ = True
        return self

    def encode(self, X: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'AutoencoderReducer 未拟合'
        Xp = X
        if self.scaler is not None:
            Xp = self.scaler.transform(Xp)
        z = self.encoder.predict(Xp, verbose=0)
        return z

    def decode(self, Z: np.ndarray) -> np.ndarray:
        assert self.fitted_, 'AutoencoderReducer 未拟合'
        Xp_hat = self.decoder.predict(Z, verbose=0)
        X_hat = self.scaler.inverse_transform(Xp_hat) if self.scaler is not None else Xp_hat
        Xc = np.empty_like(X_hat)
        for i, (low, high) in enumerate(self.bounds_):
            Xc[:, i] = np.clip(X_hat[:, i], low, high)
        return Xc


def prepare_pca_reduced_problem(objective_func: Callable,
                               bounds: List[Tuple],
                               n_components: int,
                               initial_samples: int = 200,
                               sampling_method: str = 'lhs',
                               scale: bool = True,
                               pad_ratio: float = 0.10) -> Dict[str, Any]:
    """使用 PCA 构造降维优化问题"""
    n_dims = len(bounds)
    samples = _sample_space(n_dims, initial_samples, bounds, sampling_method)

    reducer = PCAReducer(n_components=n_components, scale=scale).fit(samples, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = _compute_reduced_bounds(Z, n_components, pad_ratio)

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'pca_model': reducer,
        'samples_info': {'X': samples, 'Z': Z}
    }


def prepare_kpca_reduced_problem(objective_func: Callable,
                                bounds: List[Tuple],
                                n_components: int,
                                initial_samples: int = 300,
                                sampling_method: str = 'lhs',
                                kernel: str = 'rbf',
                                scale: bool = True,
                                decoder_alpha: float = 1.0,
                                pad_ratio: float = 0.10,
                                **kernel_kwargs) -> Dict[str, Any]:
    """使用 Kernel PCA 构造降维优化问题"""
    n_dims = len(bounds)
    samples = _sample_space(n_dims, initial_samples, bounds, sampling_method)

    reducer = KernelPCAReducer(n_components=n_components, kernel=kernel, scale=scale, **kernel_kwargs)
    reducer.decoder = Ridge(alpha=decoder_alpha)
    reducer.fit(samples, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = _compute_reduced_bounds(Z, n_components, pad_ratio)

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'kpca_model': reducer,
        'samples_info': {'X': samples, 'Z': Z}
    }


def prepare_pls_reduced_problem(objective_func: Callable,
                               bounds: List[Tuple],
                               n_components: int,
                               initial_samples: int = 200,
                               sampling_method: str = 'lhs',
                               scale: bool = True,
                               pad_ratio: float = 0.10) -> Dict[str, Any]:
    """使用 PLS 构造降维优化问题"""
    n_dims = len(bounds)
    samples = _sample_space(n_dims, initial_samples, bounds, sampling_method)
    y = np.array([objective_func(x) for x in samples], dtype=float)

    reducer = PLSReducer(n_components=n_components, scale=scale).fit(samples, y, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = _compute_reduced_bounds(Z, n_components, pad_ratio)

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'pls_model': reducer,
        'samples_info': {'X': samples, 'Z': Z, 'y': y}
    }


def prepare_autoencoder_reduced_problem(objective_func: Callable,
                                        bounds: List[Tuple],
                                        n_components: int,
                                        initial_samples: int = 500,
                                        sampling_method: str = 'lhs',
                                        scale: bool = True,
                                        epochs: int = 150,
                                        batch_size: int = 64,
                                        pad_ratio: float = 0.10) -> Dict[str, Any]:
    """使用自编码器构造降维优化问题"""
    n_dims = len(bounds)
    samples = _sample_space(n_dims, initial_samples, bounds, sampling_method)

    reducer = AutoencoderReducer(n_components=n_components, scale=scale, epochs=epochs, batch_size=batch_size)
    reducer.fit(samples, bounds)
    Z = reducer.encode(samples)

    reduced_bounds = _compute_reduced_bounds(Z, n_components, pad_ratio)

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return float(objective_func(X[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        X = reducer.decode(z)
        return X[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'autoencoder': reducer,
        'samples_info': {'X': samples, 'Z': Z}
    }


def prepare_active_subspace_reduced_problem(objective_func: Callable,
                                            bounds: List[Tuple],
                                            n_components: int,
                                            initial_samples: int = 200,
                                            sampling_method: str = 'lhs',
                                            gradient_eps: float = 1e-4,
                                            scale: bool = True,
                                            pad_ratio: float = 0.10) -> Dict[str, Any]:
    """使用 Active Subspace 构造降维优化问题"""
    n_dims = len(bounds)
    samples = _sample_space(n_dims, initial_samples, bounds, sampling_method)

    X = samples.copy()
    if scale:
        scaler = StandardScaler()
        Xp = scaler.fit_transform(X)
    else:
        scaler = None
        Xp = X

    def finite_diff_grad(x):
        g = np.zeros(n_dims)
        fx = objective_func(x)
        for i in range(n_dims):
            h = gradient_eps * (bounds[i][1] - bounds[i][0] + 1e-12)
            xh = x.copy()
            xh[i] = np.clip(xh[i] + h, bounds[i][0], bounds[i][1])
            g[i] = (objective_func(xh) - fx) / (h + 1e-12)
        return g

    grads = np.array([finite_diff_grad(x) for x in X], dtype=float)
    C = (grads.T @ grads) / max(1, grads.shape[0])
    evals, evecs = np.linalg.eigh(C)
    idx = np.argsort(evals)[::-1]
    W = evecs[:, idx[:n_components]]

    x0 = np.mean(Xp, axis=0)

    def encode_points(Xin):
        Xp_in = scaler.transform(Xin) if scaler is not None else Xin
        Z = (Xp_in - x0) @ W
        return Z

    def decode_points(Zin):
        Xp_rec = x0 + Zin @ W.T
        Xrec = scaler.inverse_transform(Xp_rec) if scaler is not None else Xp_rec
        Xc = np.empty_like(Xrec)
        for i, (low, high) in enumerate(bounds):
            Xc[:, i] = np.clip(Xrec[:, i], low, high)
        return Xc

    Z = encode_points(X)
    reduced_bounds = _compute_reduced_bounds(Z, n_components, pad_ratio)

    def reduced_objective(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        Xfull = decode_points(z)
        return float(objective_func(Xfull[0]))

    def expand_to_full(z_vec):
        z = np.asarray(z_vec, dtype=float).reshape(1, -1)
        Xfull = decode_points(z)
        return Xfull[0]

    return {
        'reduced_objective': reduced_objective,
        'reduced_bounds': reduced_bounds,
        'expand_to_full': expand_to_full,
        'active_subspace': {'W': W, 'x0': x0, 'scaler': scaler},
        'samples_info': {'X': X, 'Z': Z, 'grads': grads, 'evals': evals[idx]}
    }


def _sample_space(n_dims: int, n_samples: int, bounds: List[Tuple], method: str) -> np.ndarray:
    """空间采样"""
    if method == 'lhs':
        samples = np.zeros((n_samples, n_dims))
        for i in range(n_dims):
            samples[:, i] = np.random.permutation(n_samples) + np.random.uniform(0, 1, n_samples)
            samples[:, i] = samples[:, i] / n_samples
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    elif method == 'random':
        samples = np.random.uniform(0, 1, (n_samples, n_dims))
        for i, (low, high) in enumerate(bounds):
            samples[:, i] = low + samples[:, i] * (high - low)
    else:
        raise ValueError('不支持的采样方法')
    return samples


def _compute_reduced_bounds(Z: np.ndarray, n_components: int, pad_ratio: float) -> List[Tuple]:
    """计算降维空间的边界"""
    reduced_bounds = []
    for j in range(n_components):
        z_min, z_max = float(np.min(Z[:, j])), float(np.max(Z[:, j]))
        span = z_max - z_min
        pad = max(1e-6, pad_ratio * span)
        reduced_bounds.append((z_min - pad, z_max + pad))
    return reduced_bounds
