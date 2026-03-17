#!/usr/bin/env python3
"""
基于拓扑排序的并行调度器
核心职责：
1. 从 workflow.yaml 构建 DAG
2. 拓扑排序获取可执行步骤
3. 并行执行独立步骤
4. 统一处理 Gate 检查
"""

import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class ParallelScheduler:
    """基于 DAG 的并行工作流调度器"""

    def __init__(self, orchestrator, workflow: Dict, run_context):
        self.orch = orchestrator
        self.workflow = workflow
        self.context = run_context

    def run(self, start_from: Optional[str] = None):
        """执行 DAG，自动处理并行和依赖"""
        dag = self._build_dag()

        if start_from:
            self._reset_from_step(dag, start_from)

        while True:
            ready = self._get_ready_steps(dag)

            if not ready:
                if self._all_done(dag):
                    break
                time.sleep(0.5)  # 等待运行中步骤
                continue

            if self._has_gate(ready):
                if not self._handle_gate(ready):
                    break  # 等待用户确认

            self._execute_parallel(ready, dag)

    def _build_dag(self) -> Dict:
        """从 workflow.yaml 构建邻接表"""
        dag = {}
        for step_key, config in self.workflow["steps"].items():
            # 获取对应的 Orchestrator 方法
            step_fn = getattr(self.orch, config["fn"], None)
            if step_fn is None:
                raise ValueError(f"Step function not found: {config['fn']}")

            dag[step_key] = {
                "id": config["id"],
                "fn": step_fn,
                "deps": config["deps"],  # 依赖的 step_key 列表
                "gate": config.get("gate", False)
            }
        return dag

    def _get_ready_steps(self, dag: Dict) -> List[str]:
        """拓扑排序：返回无阻塞的步骤"""
        ready = []
        for step_key, config in dag.items():
            step_id = config["id"]
            state = self.context.get_step_state(step_id)
            if state != "PENDING":
                continue

            # 检查依赖是否全部完成
            deps_done = all(
                self.context.get_step_state(dag[dep_key]["id"]) == "DONE"
                for dep_key in config["deps"]
            )
            if deps_done:
                ready.append(step_key)
        return ready

    def _has_gate(self, ready_step_keys: List[str]) -> bool:
        """检查是否有 Gate 点"""
        for step_key in ready_step_keys:
            if self.workflow["steps"][step_key].get("gate", False):
                return True
        return False

    def _handle_gate(self, ready_step_keys: List[str]) -> bool:
        """处理 Gate 点，返回是否继续执行"""
        for step_key in ready_step_keys:
            step_config = self.workflow["steps"][step_key]
            if step_config.get("gate", False):
                step_id = step_config["id"]
                if step_id == "05_draft":
                    return self.orch.check_gate_a()
                elif step_id == "08_prompts":
                    return self.orch.check_gate_b()
        return True

    def _execute_parallel(self, step_keys: List[str], dag: Dict):
        """并行执行多个步骤"""
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for step_key in step_keys:
                config = dag[step_key]
                future = executor.submit(
                    self._run_step,
                    config["id"],
                    config["fn"]
                )
                futures[future] = step_key

            for future in as_completed(futures):
                step_key = futures[future]
                try:
                    future.result()
                except Exception as e:
                    step_id = dag[step_key]["id"]
                    self.context.update_step_state(step_id, "FAILED")
                    raise

    def _run_step(self, step_id: str, fn: Callable):
        """执行单个步骤"""
        self.context.update_step_state(step_id, "RUNNING")
        result = fn()
        artifacts = result.get("artifacts", []) if isinstance(result, dict) else []
        self.context.update_step_state(step_id, "DONE", artifacts)

    def _all_done(self, dag: Dict) -> bool:
        """检查是否所有步骤完成"""
        for config in dag.values():
            if self.context.get_step_state(config["id"]) != "DONE":
                return False
        return True

    def _reset_from_step(self, dag: Dict, start_from: str):
        """从指定步骤重置（用于 --resume --start-from）"""
        # 找到 start_from 对应的 step_key
        target_key = None
        for step_key, config in dag.items():
            if config["id"] == start_from:
                target_key = step_key
                break

        if target_key is None:
            raise ValueError(f"Invalid step_id: {start_from}")

        # 重置该步骤及所有后续步骤为 PENDING
        to_reset = self._get_descendants(dag, target_key)
        for step_key in to_reset:
            step_id = dag[step_key]["id"]
            self.context.update_step_state(step_id, "PENDING")

    def _get_descendants(self, dag: Dict, step_key: str) -> List[str]:
        """获取步骤的所有后代（包括自己）"""
        descendants = set()
        to_visit = [step_key]

        while to_visit:
            current = to_visit.pop()
            if current in descendants:
                continue
            descendants.add(current)

            # 找到所有依赖 current 的步骤
            for other_key, config in dag.items():
                if current in config["deps"] and other_key not in descendants:
                    to_visit.append(other_key)

        return list(descendants)


def load_workflow() -> Dict:
    """加载 workflow.yaml"""
    workflow_file = Path(__file__).parent / "workflow.yaml"
    if not workflow_file.exists():
        raise FileNotFoundError(f"workflow.yaml not found: {workflow_file}")

    with open(workflow_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
