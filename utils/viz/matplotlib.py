import time
from typing import Any, Dict, Tuple

import numpy as np

# Matplotlib is optional. Import lazily so `import nsgablack` works without it.
plt = None
animation = None
Button = None
Slider = None
TextBox = None


def _lazy_import_matplotlib() -> None:
    global plt, animation, Button, Slider, TextBox
    if plt is not None:
        return

    import matplotlib.pyplot as _plt  # type: ignore
    import matplotlib.animation as _animation  # type: ignore
    from matplotlib.widgets import Button as _Button, Slider as _Slider, TextBox as _TextBox  # type: ignore

    _plt.rcParams["font.sans-serif"] = [
        "SimHei",
        "Arial Unicode MS",
        "Microsoft YaHei",
        "WenQuanYi Micro Hei",
    ]
    _plt.rcParams["axes.unicode_minus"] = False
    _plt.rcParams["animation.embed_limit"] = 20.0

    plt = _plt
    animation = _animation
    Button = _Button
    Slider = _Slider
    TextBox = _TextBox


class SolverVisualizationMixin:
    """Matplotlib-based visualization mixin for the NSGA-II solver."""

    def _init_visualization(self) -> None:
        _lazy_import_matplotlib()
        self.plot_enabled = False
        self.visualization_update_frequency = 5
        self.last_viz_update = 0
        self.max_display_points = 200
        self.animation = None
        self.bound_textboxes: Dict[Tuple[str, str], Any] = {}
        self.fig = plt.figure(figsize=(14, 9))
        gridspec = self.fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.5])
        self.ax_func = self.fig.add_subplot(gridspec[0, 0])
        self.ax_fitness = self.fig.add_subplot(gridspec[1, 0])
        self.ax_info = self.fig.add_subplot(gridspec[0:2, 1])
        self.ax_controls = self.fig.add_subplot(gridspec[2, :])
        self.fig.suptitle(f'NSGA-II求解黑箱问题: {self.problem.name}', fontsize=16)
        self.plot_cache = {
            'population_scatter': None,
            'pareto_scatter': None,
            'pareto_line': None,
            'fitness_lines': []
        }
        self.setup_ui()
        self.update_info_text()

    def setup_ui(self) -> None:
        self.ax_info.axis('off')
        self.ax_controls.axis('off')
        self.info_text = self.ax_info.text(0.02, 0.95, '', fontsize=10, verticalalignment='top')
        plot_btn_ax = plt.axes([0.55, 0.15, 0.12, 0.07])
        self.btn_toggle_plot = Button(plot_btn_ax, '开启绘图', color='#FFFF99')
        self.btn_toggle_plot.on_clicked(self.toggle_plot)
        diversity_btn_ax = plt.axes([0.55, 0.07, 0.12, 0.07])
        self.btn_toggle_diversity = Button(diversity_btn_ax, '关闭多样性初始化', color='#CCFFCC')
        self.btn_toggle_diversity.on_clicked(self.toggle_diversity_init)
        history_btn_ax = plt.axes([0.55, -0.01, 0.12, 0.07])
        self.btn_toggle_history = Button(history_btn_ax, '关闭历史数据', color='#FFCCCC')
        self.btn_toggle_history.on_clicked(self.toggle_history)
        elite_btn_ax = plt.axes([0.68, -0.01, 0.12, 0.07])
        self.btn_toggle_elite = Button(elite_btn_ax, '开启精英保留', color='#CCCCFF')
        self.btn_toggle_elite.on_clicked(self.toggle_elite_retention)
        run_btn_ax = plt.axes([0.1, 0.15, 0.1, 0.07])
        self.btn_run = Button(run_btn_ax, '运行', color='#90EE90')
        self.btn_run.on_clicked(self.run_algorithm)
        stop_btn_ax = plt.axes([0.25, 0.15, 0.1, 0.07])
        self.btn_stop = Button(stop_btn_ax, '停止', color='#FFB6C1')
        self.btn_stop.on_clicked(self.stop_algorithm)
        reset_btn_ax = plt.axes([0.4, 0.15, 0.1, 0.07])
        self.btn_reset = Button(reset_btn_ax, '重置', color='#F0E68C')
        self.btn_reset.on_clicked(self.reset)
        pop_box_ax = plt.axes([0.68, 0.22, 0.08, 0.05])
        self.pop_box = TextBox(pop_box_ax, '种群: ', initial=str(self.pop_size))
        self.pop_box.on_submit(self.update_pop_size)
        gen_box_ax = plt.axes([0.78, 0.22, 0.08, 0.05])
        self.gen_box = TextBox(gen_box_ax, '代数: ', initial=str(self.max_generations))
        self.gen_box.on_submit(self.update_max_generations)
        mut_slider_ax = plt.axes([0.68, 0.15, 0.18, 0.05])
        self.mutation_slider = Slider(mut_slider_ax, '变异率', 0.01, 0.5, valinit=self.mutation_rate)
        self.mutation_slider.on_changed(self.update_mutation_rate)
        elite_slider_ax = plt.axes([0.88, 0.15, 0.08, 0.05])
        self.elite_slider = Slider(elite_slider_ax, '精英概率', 0.1, 1.0, valinit=self.elite_retention_prob)
        self.elite_slider.on_changed(self.update_elite_prob)
        candidate_box_ax = plt.axes([0.68, 0.07, 0.08, 0.05])
        self.candidate_box = TextBox(candidate_box_ax, '候选解: ', initial=str(self.diversity_params['candidate_size']))
        self.candidate_box.on_submit(self.update_candidate_size)
        threshold_box_ax = plt.axes([0.78, 0.07, 0.08, 0.05])
        self.threshold_box = TextBox(threshold_box_ax, '相似阈值: ', initial=str(self.diversity_params['similarity_threshold']))
        self.threshold_box.on_submit(self.update_similarity_threshold)
        rejection_box_ax = plt.axes([0.88, 0.07, 0.08, 0.05])
        self.rejection_box = TextBox(rejection_box_ax, '拒绝概率: ', initial=str(self.diversity_params['rejection_prob']))
        self.rejection_box.on_submit(self.update_rejection_prob)
        bound_y_pos = -0.01
        for index, var in enumerate(self.variables):
            var_label_ax = plt.axes([0.1 + index * 0.2, bound_y_pos, 0.05, 0.04])
            var_label_ax.axis('off')
            var_label_ax.text(0.5, 0.5, f'{var}:', ha='center', va='center', fontsize=9)
            min_box_ax = plt.axes([0.13 + index * 0.2, bound_y_pos, 0.04, 0.04])
            min_box = TextBox(min_box_ax, '', initial=str(self.var_bounds[var][0]))
            min_box.on_submit(lambda text, variable=var, bound='min': self.update_var_bound(variable, bound, text))
            max_box_ax = plt.axes([0.18 + index * 0.2, bound_y_pos, 0.04, 0.04])
            max_box = TextBox(max_box_ax, '', initial=str(self.var_bounds[var][1]))
            max_box.on_submit(lambda text, variable=var, bound='max': self.update_var_bound(variable, bound, text))
            self.bound_textboxes[(var, 'min')] = min_box
            self.bound_textboxes[(var, 'max')] = max_box

    def toggle_elite_retention(self, _event) -> None:
        self.enable_elite_retention = not self.enable_elite_retention
        if self.enable_elite_retention:
            self.btn_toggle_elite.label.set_text('关闭精英保留')
            self.btn_toggle_elite.color = '#FFCCCC'
        else:
            self.btn_toggle_elite.label.set_text('开启精英保留')
            self.btn_toggle_elite.color = '#CCCCFF'
        self.update_info_text()

    def update_elite_prob(self, value: float) -> None:
        self.elite_retention_prob = value
        self.elite_manager.initial_retention_prob = value

    def toggle_diversity_init(self, _event) -> None:
        self.enable_diversity_init = not self.enable_diversity_init
        if self.enable_diversity_init:
            self.btn_toggle_diversity.label.set_text('开启多样性初始化')
            self.btn_toggle_diversity.color = '#90EE90'
            if self.use_history:
                self.diversity_initializer.load_history()
        else:
            self.btn_toggle_diversity.label.set_text('关闭多样性初始化')
            self.btn_toggle_diversity.color = '#CCFFCC'
        self.update_info_text()

    def toggle_history(self, _event) -> None:
        self.use_history = not self.use_history
        if self.use_history:
            self.btn_toggle_history.label.set_text('开启历史数据')
            self.btn_toggle_history.color = '#90EE90'
            if self.enable_diversity_init:
                self.diversity_initializer.load_history()
        else:
            self.btn_toggle_history.label.set_text('关闭历史数据')
            self.btn_toggle_history.color = '#FFCCCC'
        self.update_info_text()

    def toggle_plot(self, _event) -> None:
        if not self.plot_enabled:
            self.plot_enabled = True
            self.btn_toggle_plot.label.set_text('关闭绘图')
            self.init_plot_static_elements()
            if self.population is not None:
                self.update_plot_dynamic()
        else:
            self.plot_enabled = False
            self.btn_toggle_plot.label.set_text('开启绘图')
            self.clear_all_plots()

    def clear_all_plots(self) -> None:
        if not self.plot_enabled:
            if self.plot_cache['population_scatter'] is not None:
                self.plot_cache['population_scatter'].remove()
            if self.plot_cache['pareto_scatter'] is not None:
                self.plot_cache['pareto_scatter'].remove()
            if self.plot_cache['pareto_line'] is not None:
                for line in self.plot_cache['pareto_line']:
                    line.remove()
            for line in self.plot_cache['fitness_lines']:
                line.remove()
            self.plot_cache = {
                'population_scatter': None,
                'pareto_scatter': None,
                'pareto_line': None,
                'fitness_lines': []
            }
            plt.draw()

    def init_plot_static_elements(self) -> None:
        if not self.plot_enabled:
            return
        self.ax_func.set_title('解空间与Pareto前沿')
        self.ax_func.set_xlabel(self.variables[0] if self.dimension >= 1 else '变量1')
        self.ax_func.set_ylabel(self.variables[1] if self.dimension >= 2 else '变量2')
        self.ax_func.grid(True, alpha=0.3)
        self.ax_fitness.set_title('各前沿平均目标值进化')
        self.ax_fitness.set_xlabel('代数')
        self.ax_fitness.set_ylabel('平均目标值')
        self.ax_fitness.grid(True, alpha=0.3)
        self.ax_fitness.set_xlim(0, self.max_generations)
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='skyblue', markersize=8, label='普通个体'),
            plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='Pareto最优解'),
            plt.Line2D([0], [0], color='orange', linewidth=2, label='Pareto前沿')
        ]
        self.ax_func.legend(handles=legend_elements, loc='upper right', fontsize=9)

    def redraw_static_elements(self) -> None:
        if not self.plot_enabled:
            return
        self.ax_func.clear()
        self.ax_fitness.clear()
        self.init_plot_static_elements()
        plt.draw()

    def update_plot_dynamic(self) -> None:
        if not self.plot_enabled:
            return
        self.update_population_and_pareto_plot()
        self.update_fitness_plot()
        plt.tight_layout()
        plt.draw()

    def update_population_and_pareto_plot(self) -> None:
        if not self.plot_enabled:
            return
        if self.plot_cache['population_scatter'] is not None:
            self.plot_cache['population_scatter'].remove()
        if self.plot_cache['pareto_scatter'] is not None:
            self.plot_cache['pareto_scatter'].remove()
        if self.plot_cache['pareto_line'] is not None:
            for line in self.plot_cache['pareto_line']:
                line.remove()
        if self.population is not None and self.dimension >= 2:
            scatter = self.ax_func.scatter(
                self.population[:, 0], self.population[:, 1],
                c='skyblue', s=30, alpha=0.6, marker='o'
            )
            self.plot_cache['population_scatter'] = scatter
        if (
            self.pareto_solutions is not None and
            len(self.pareto_solutions['individuals']) > 0 and
            self.dimension >= 2
        ):
            pareto_individuals = self.pareto_solutions['individuals']
            scatter_pareto = self.ax_func.scatter(
                pareto_individuals[:, 0], pareto_individuals[:, 1],
                c='red', s=60, alpha=0.8, marker='o'
            )
            self.plot_cache['pareto_scatter'] = scatter_pareto
            if self.num_objectives == 2 and len(pareto_individuals) > 1:
                sorted_idx = np.argsort(self.pareto_solutions['objectives'][:, 0])
                obj1_sorted = self.pareto_solutions['objectives'][sorted_idx, 0]
                obj2_sorted = self.pareto_solutions['objectives'][sorted_idx, 1]
                line = self.ax_fitness.plot(obj1_sorted, obj2_sorted, 'orange', linewidth=2)
                self.plot_cache['pareto_line'] = line
            else:
                self.plot_cache['pareto_line'] = None
        else:
            self.plot_cache['pareto_scatter'] = None
            self.plot_cache['pareto_line'] = None

    def update_fitness_plot(self) -> None:
        if not self.plot_enabled:
            return
        for line in self.plot_cache['fitness_lines']:
            line.remove()
        self.plot_cache['fitness_lines'].clear()
        if not self.history:
            return
        generations = [entry[0] for entry in self.history]
        max_rank = min(2, len(self.history[0][1]))
        if self.num_objectives == 1:
            best_fitness = [entry[1][0][0] for entry in self.history if not np.isnan(entry[1][0][0])]
            if len(best_fitness) == len(generations):
                line, = self.ax_fitness.plot(generations, best_fitness, 'b-', linewidth=2, label='最佳适应度')
                self.plot_cache['fitness_lines'].append(line)
        else:
            for rank_idx in range(max_rank):
                for obj_idx in range(min(2, self.num_objectives)):
                    avg_obj = [
                        entry[1][rank_idx][obj_idx]
                        for entry in self.history
                        if not np.isnan(entry[1][rank_idx][obj_idx])
                    ]
                    if len(avg_obj) == len(generations):
                        label = f'第{rank_idx + 1}前沿（目标{obj_idx + 1}平均）'
                        line, = self.ax_fitness.plot(generations, avg_obj, f'C{obj_idx}', linewidth=2, label=label)
                        self.plot_cache['fitness_lines'].append(line)
        self.ax_fitness.legend(fontsize=9)

    def update_info_text(self) -> None:
        info = "NSGA-II求解黑箱问题\n"
        info += f"问题: {self.problem.name}\n"
        info += f"绘图状态: {'开启' if self.plot_enabled else '关闭'}\n"
        info += f"多样性初始化: {'开启' if self.enable_diversity_init else '关闭'}\n"
        info += f"历史数据: {'开启' if self.use_history else '关闭'}\n"
        info += f"精英保留策略: {'开启' if self.enable_elite_retention else '关闭'}\n"
        if self.enable_elite_retention:
            info += f"精英保留概率: {self.elite_retention_prob:.2f}\n"
        info += f"变量: {', '.join(self.variables)} (维度: {self.dimension})\n"
        info += "变量限制:\n"
        for var, (min_val, max_val) in self.var_bounds.items():
            info += f"  {var} ∈ [{min_val:.2f}, {max_val:.2f}]\n"
        info += f"目标数: {self.num_objectives}\n"
        info += f"种群大小: {self.pop_size}, 最大代数: {self.max_generations}\n"
        info += f"变异率: {self.mutation_rate:.2f}\n"
        info += f"函数评估次数: {self.evaluation_count}\n"
        if self.enable_diversity_init:
            info += "\n多样性初始化参数:\n"
            info += f"  候选解数量: {self.diversity_params['candidate_size']}\n"
            info += f"  相似度阈值: {self.diversity_params['similarity_threshold']:.3f}\n"
            info += f"  拒绝概率: {self.diversity_params['rejection_prob']:.2f}\n"
            info += f"  历史解数量: {len(self.diversity_initializer.history_solutions)}\n"
        if self.pareto_solutions is not None:
            num_pareto = len(self.pareto_solutions['individuals'])
            info += f"\nPareto最优解数量: {num_pareto}\n"
            for index, (ind, obj) in enumerate(zip(self.pareto_solutions['individuals'][:2], self.pareto_solutions['objectives'][:2])):
                info += f"解{index + 1}: "
                for var, val in zip(self.variables, ind):
                    info += f"{var}={val:.4f}, "
                formatted_obj = ', '.join([f'{value:.4f}' for value in obj])
                info += f"目标=[{formatted_obj}]\n"
        if self.running:
            elapsed_time = time.time() - self.start_time
            info += f"\n运行状态: 第{self.generation}代\n"
            info += f"运行时间: {elapsed_time:.2f}秒\n"
        if self.enable_convergence_detection and self.convergence_state['status'] != 'INIT':
            state = self.convergence_state
            info += f"\n收敛判定: {state['status']}\n"
            if state['best_f'] is not None:
                info += f"参考最优: {state['best_f']:.6g}\n"
            if state['current_diversity'] is not None:
                info += f"多样性: {state['current_diversity']:.4f}\n"
            info += f"停滞计数: {state['stagnation_counter']}\n"
            if state['noise_std'] is not None:
                info += f"噪声STD: {state['noise_std']:.3g}\n"
        self.info_text.set_text(info)

    def start_animation(self) -> None:
        if self.animation:
            self.animation.event_source.stop()
        self.animation = animation.FuncAnimation(
            self.fig,
            self.animate,
            frames=self.max_generations,
            interval=200,
            repeat=False,
            blit=False
        )
        plt.draw()

    def stop_animation(self) -> None:
        if self.animation:
            self.animation.event_source.stop()


__all__ = ['SolverVisualizationMixin']
