import argparse
import json
import yaml
import random
import time
import os
import re
from collections import deque, defaultdict


class Service:
    def __init__(self, name, depends_on, health):
        self.name = name
        self.depends_on = set(depends_on)
        self.health = float(health)
        self.initial_health = float(health)
        self.is_failed = False
        self.failed_at_tick = -1
        self.recovery_timer = -1

    def __repr__(self):
        return f"Service({self.name}, health={self.health:.2f})"


class ServiceGraph:
    def __init__(self, services_data):
        self.services = {s['name']: Service(s['name'], s.get('depends_on', []), s['health']) for s in services_data}
        self.adj = {name: service.depends_on for name, service in self.services.items()}
        self.rev_adj = self.build_reverse_adjacency()
        self.cycles = []
        self.sorted_services = self.topological_sort()
        self.name_index_lower = {name.lower(): name for name in self.services.keys()}

    def build_reverse_adjacency(self):
        rev_adj = defaultdict(set)
        for name, service in self.services.items():
            for dep in service.depends_on:
                if dep in self.services:
                    rev_adj[dep].add(name)
        return rev_adj

    def topological_sort(self):
        in_degree = {name: 0 for name in self.services}
        for name, service in self.services.items():
            for dep in service.depends_on:
                if dep in in_degree:
                    in_degree[name] += 1

        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        sorted_order = []

        while queue:
            u = queue.popleft()
            sorted_order.append(u)

            for v_name in self.rev_adj.get(u, []):
                in_degree[v_name] -= 1
                if in_degree[v_name] == 0:
                    queue.append(v_name)

        if len(sorted_order) != len(self.services):
            visited = set()
            path = []
            for node in self.services:
                if node not in visited:
                    self.find_cycle_util(node, visited, path, [])
            return None

        return [self.services[name] for name in sorted_order]

    def find_cycle_util(self, node, visited, recursion_stack, path):
        visited.add(node)
        recursion_stack.append(node)
        path.append(node)

        for neighbor in self.adj.get(node, []):
            if neighbor not in self.services:
                continue
            if neighbor in recursion_stack:
                try:
                    cycle_start_index = recursion_stack.index(neighbor)
                    cycle = recursion_stack[cycle_start_index:] + [neighbor]
                    if sorted(cycle) not in [sorted(c) for c in self.cycles]:
                        self.cycles.append(cycle)
                except ValueError:
                    pass
            elif neighbor not in visited:
                self.find_cycle_util(neighbor, visited, recursion_stack, path)

        recursion_stack.pop()
        path.pop()


class Simulator:
    def __init__(self, graph, config):
        self.graph = graph
        self.config = config
        self.tick = 0
        self.output_dir = f"runs/{time.strftime('%Y%m%d-%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.output_dir, 'output.log')
        random.seed(self.config['seed'])

        self.events = []
        self.incident_log = []
        self.service_degradation_history = defaultdict(list)

    def log(self, message):
        print(message)
        with open(self.log_file_path, 'a') as f:
            f.write(message + '\n')

    def run(self):
        start_time = time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime())
        self.log(f"# The Domino Effect Challenge - Simulation Log")
        self.log(f"# Run: {self.config['ticks']} ticks, threshold={self.config['threshold']}, seed={self.config['seed']}")
        self.log(f"# Start: {start_time}\n")

        if not self.graph.sorted_services:
            for cycle in self.graph.cycles:
                self.log(f"[WARN] Cycle detected: {' -> '.join(cycle)} (RCA may be approximate)")
            self.graph.sorted_services = list(self.graph.services.values())

        self.log(f"[BOOT] Loaded {len(self.graph.services)} services.")

        for self.tick in range(1, self.config['ticks'] + 1):
            self.log(f"\n[TICK {self.tick}] {time.strftime('%H:%M:%S', time.localtime())}")
            self.run_tick()

        end_time = time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime())
        self.log(f"\n# End: {end_time}")

    def run_tick(self):
        
        for service in self.graph.services.values():
            service.initial_health = service.health
            self.service_degradation_history[service.name].append({
                'tick': self.tick,
                'health': service.health,
                'is_failed': service.is_failed
            })

        glitched_service = self.apply_glitch()
        if glitched_service:
            self.log(f"[GLITCH] {glitched_service.name} health {glitched_service.initial_health:.2f} -> {glitched_service.health:.2f} (random glitch)")
            self.events.append({
                'tick': self.tick,
                'type': 'glitch',
                'service': glitched_service.name,
                'old_health': glitched_service.initial_health,
                'new_health': glitched_service.health
            })

        self.handle_recovery()
        self.propagate_health()

        failed_services = [s for s in self.graph.services.values() if s.health < self.config['threshold']]

        if not failed_services:
            min_health_service = min(self.graph.services.values(), key=lambda s: s.health)
            self.log(f"[INFO] All services healthy (min health={min_health_service.health:.2f} on {min_health_service.name})")
            return

        newly_failed = [s for s in failed_services if not s.is_failed]
        for service in newly_failed:
            service.is_failed = True
            service.failed_at_tick = self.tick
            service.recovery_timer = self.config.get('cooldown', -1)
            self.log(f"[ALERT] {service.name} fell below threshold ({service.health:.2f} < {self.config['threshold']})")
            self.events.append({
                'tick': self.tick,
                'type': 'failure',
                'service': service.name,
                'health': service.health
            })

        if newly_failed:
            self.perform_rca(failed_services)

    def apply_glitch(self):
        eligible = [s for s in self.graph.services.values() if s.health >= self.config['threshold']]
        if not eligible:
            return None

        victim = random.choice(eligible)
        glitch_delta = random.uniform(0.2, 0.5)
        victim.health = max(0, victim.health - glitch_delta)
        return victim

    def propagate_health(self):
        threshold = self.config['threshold']
        alpha = self.config['alpha']

        for _ in range(len(self.graph.services)):
            changed = False

            for service in self.graph.services.values():
                if not service.depends_on:
                    continue

                total_degradation = 0
                for dep_name in service.depends_on:
                    dep = self.graph.services.get(dep_name)
                    if dep and dep.health < threshold:
                        total_degradation += alpha * (threshold - dep.health)

                if total_degradation > 0:
                    new_health = max(0, service.initial_health - total_degradation)
                    if abs(new_health - service.health) > 0.001:
                        service.health = new_health
                        changed = True

            if not changed:
                break

    def handle_recovery(self):
        if 'cooldown' not in self.config:
            return

        services_to_heal = []

        for service in self.graph.services.values():
            if service.is_failed and service.recovery_timer > 0:
                service.recovery_timer -= 1

            if service.recovery_timer == 0:
                services_to_heal.append(service)

        for service in services_to_heal:
            service.health = self.config['heal_to']
            service.is_failed = False
            service.recovery_timer = -1
            self.log(f"[HEAL] {service.name} -> health {service.health:.2f} at T={self.tick}")
            self.propagate_recovery(service.name)

    def propagate_recovery(self, healed_service_name):
        recovered = []
        threshold = self.config['threshold']
        queue = deque([healed_service_name])
        visited = {healed_service_name}

        while queue:
            current = queue.popleft()
            for dependent_name in self.graph.rev_adj.get(current, []):
                if dependent_name in visited:
                    continue

                dependent = self.graph.services[dependent_name]
                all_deps_healthy = all(
                    self.graph.services[dep].health >= threshold
                    for dep in dependent.depends_on
                    if dep in self.graph.services
                )

                if all_deps_healthy and dependent.health < self.config['heal_to']:
                    old_health = dependent.health
                    improvement = (self.config['heal_to'] - old_health) * 0.5
                    dependent.health = min(1.0, old_health + improvement)
                    recovered.append((dependent_name, old_health, dependent.health))

                    if dependent.health >= threshold:
                        dependent.is_failed = False
                        dependent.recovery_timer = -1

                    visited.add(dependent_name)
                    queue.append(dependent_name)

        if recovered:
            self.log(f"[RECOVERY] Upstream recovery after {healed_service_name} heal:")
            for dep_name, old_h, new_h in recovered:
                self.log(f"           - {dep_name} {old_h:.2f} -> {new_h:.2f}")

    def perform_rca(self, failed_services):
        root_causes = []
        for service in failed_services:
            is_root = True
            for dep_name in service.depends_on:
                if self.graph.services.get(dep_name) and self.graph.services[dep_name].is_failed:
                    is_root = False
                    break
            if is_root:
                root_causes.append(service)

        if not root_causes and failed_services:
            root_causes = [min(failed_services, key=lambda s: s.health)]
            self.log("[INFO] No clear root cause; prioritizing lowest health service.")

        blast_radii = {root.name: self.get_blast_radius(root.name) for root in root_causes}
        for root_name, radius in blast_radii.items():
            if radius:
                self.log(f"[BLAST] due to {root_name} -> impacted: {list(radius)}")

        sorted_roots = sorted(root_causes, key=lambda s: len(blast_radii.get(s.name, [])), reverse=True)

        root_names = [r.name for r in sorted_roots]
        self.log(f"[PRIORITY] roots={{{', '.join(r.name for r in root_causes)}}}, order={root_names}")
        if sorted_roots:
            self.log(f"[SUGGESTION] Remediate {sorted_roots[0].name} first")

        
        if sorted_roots:
            self.incident_log.append({
                'tick': self.tick,
                'roots': [r.name for r in root_causes],
                'impacted': {r.name: list(blast_radii[r.name]) for r in root_causes},
                'priority': sorted_roots[0].name
            })

    def get_blast_radius(self, start_node):
        q, visited, impacted = deque([start_node]), {start_node}, set()
        while q:
            curr = q.popleft()
            for neighbor in self.graph.rev_adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    impacted.add(neighbor)
                    q.append(neighbor)
        return impacted


class QueryHandler:
    def __init__(self, simulator):
        self.simulator = simulator
        self.graph = simulator.graph

    def query_why_failing(self, service_name):
        if service_name not in self.graph.services:
            return f"[ERROR] Service '{service_name}' not found."

        service = self.graph.services[service_name]

        if service.health >= self.simulator.config['threshold']:
            return f"[OK] {service_name} is currently healthy (health={service.health:.2f})"

        failed_at = service.failed_at_tick if service.failed_at_tick > 0 else "unknown"
        failed_deps = [d for d in service.depends_on if self.graph.services[d].health < self.simulator.config['threshold']]

        explanation = f"\n[QUERY] WHY IS {service_name.upper()} FAILING?\n{'='*60}\n\n"
        explanation += f"Current Health: {service.health:.2f} (threshold: {self.simulator.config['threshold']})\n"
        explanation += f"Failed at Tick: {failed_at}\n\n"

        if not failed_deps:
            explanation += f"[ROOT CAUSE] {service_name} failed independently\n"
            glitch_events = [e for e in self.simulator.events if e['type'] == 'glitch' and e['service'] == service_name]
            if glitch_events:
                g = glitch_events[-1]
                explanation += f"   Glitch at tick {g['tick']}: {g['old_health']:.2f} -> {g['new_health']:.2f}\n"
        else:
            explanation += f"[CASCADE FAILURE] {service_name} failed due to upstream dependencies\n\n"
            explanation += "Failed Dependencies:\n"
            for dep in failed_deps:
                d = self.graph.services[dep]
                explanation += f"  - {dep}: health={d.health:.2f}, failed at tick {d.failed_at_tick}\n"

        blast = self.graph.rev_adj.get(service_name, set())
        if blast:
            explanation += f"\n[BLAST RADIUS] {len(blast)} services depend on this\n"
            explanation += f"   Dependents: {', '.join(sorted(blast))}\n"

        return explanation

    def query_last_n_ticks(self, n=10):
        current_tick = self.simulator.tick
        start_tick = max(1, current_tick - n + 1)

        explanation = f"\n[QUERY] SUMMARY: Last {n} Ticks ({start_tick} to {current_tick})\n{'='*60}\n"

        recent_events = [e for e in self.simulator.events if e['tick'] >= start_tick]
        recent_incidents = [i for i in self.simulator.incident_log if i['tick'] >= start_tick]

        for tick in range(start_tick, current_tick + 1):
            tick_events = [e for e in recent_events if e['tick'] == tick]
            tick_incidents = [i for i in recent_incidents if i['tick'] == tick]

            if tick_events or tick_incidents:
                explanation += f"\n[TICK {tick}]\n"
                for e in [x for x in tick_events if x['type'] == 'glitch']:
                    explanation += f"  [GLITCH] {e['service']} ({e['old_health']:.2f} -> {e['new_health']:.2f})\n"
                for e in [x for x in tick_events if x['type'] == 'failure']:
                    explanation += f"  [FAILURE] {e['service']} (health={e['health']:.2f})\n"
                for inc in tick_incidents:
                    explanation += f"  [ROOT CAUSE] {', '.join(inc['roots'])}\n"

        explanation += f"\n[STATISTICS]\n"
        explanation += f"  Total Glitches: {len([e for e in recent_events if e['type'] == 'glitch'])}\n"
        explanation += f"  Total Failures: {len([e for e in recent_events if e['type'] == 'failure'])}\n"

        return explanation

    def query_top_impacted(self):
        explanation = f"\n[QUERY] TOP IMPACTED SERVICES\n{'='*60}\n\n"

        scores = {}
        for name, history in self.simulator.service_degradation_history.items():
            initial = history[0]['health'] if history else 1.0
            current = self.graph.services[name].health
            failures = sum(1 for h in history if h['is_failed'])
            avg = sum(h['health'] for h in history) / len(history) if history else 1.0

            scores[name] = {
                'degradation': initial - current,
                'failures': failures,
                'avg': avg,
                'current': current
            }

        sorted_svc = sorted(
            scores.items(),
            key=lambda x: (x[1]['failures'], x[1]['degradation']),
            reverse=True
        )

        explanation += "Rank | Service    | Failures | Degradation | Avg Health | Current\n"
        explanation += "-----+------------+----------+-------------+------------+---------\n"

        for rank, (name, s) in enumerate(sorted_svc[:10], 1):
            explanation += f"{rank:4d} | {name:10s} | {s['failures']:8d} | {s['degradation']:11.2f} | {s['avg']:10.2f} | {s['current']:7.2f}\n"

        return explanation



def _normalize_service_name(graph, token):
    if not token:
        return None
    if token in graph.services:
        return token
    cleaned = token.rstrip('?.!,;:').strip()
    if cleaned in graph.services:
        return cleaned
    return graph.name_index_lower.get(cleaned.lower())


def handle_query(query_handler, query_text):
    q = query_text.strip()
    q_lower = q.lower()

    if q_lower.startswith("why is") and "failing" in q_lower:
        m = re.search(r'why is\s+([A-Za-z0-9_\-]+)', q, flags=re.IGNORECASE)
        if m:
            token = m.group(1).rstrip('?.!,;:').strip()
            canonical = _normalize_service_name(query_handler.graph, token)
            if canonical:
                return query_handler.query_why_failing(canonical)
            return f"[ERROR] Service '{token}' not found."
        return "[ERROR] Could not parse service name"

    elif "what happened" in q_lower:
        m = re.search(r'last\s+(\d+)', q_lower)
        n = int(m.group(1)) if m else 10
        return query_handler.query_last_n_ticks(n)

    elif "top-impacted" in q_lower or "top impacted" in q_lower:
        return query_handler.query_top_impacted()

    else:
        return "[ERROR] Unknown query. Try: 'why is <service> failing?', 'what happened in the last N ticks?', 'top-impacted'"


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--input', default='services.json')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--query', help='Single query after simulation')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive query mode')
    args = parser.parse_args()

    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config {args.config}: {e}")
        return

    try:
        with open(args.input, 'r') as f:
            services_data = json.load(f)
    except Exception as e:
        print(f"Error loading services {args.input}: {e}")
        return

    service_graph = ServiceGraph(services_data)
    simulator = Simulator(service_graph, config)

    simulator.run()
    print(f"\nSimulation complete. Log file at: {simulator.log_file_path}")

    
    if args.query:
        query_handler = QueryHandler(simulator)
        print(handle_query(query_handler, args.query))

    elif args.interactive:
        print(f"\n{'='*60}\n[INTERACTIVE QUERY MODE]\n{'='*60}")
        print("\nAvailable queries:")
        print("  - why is <service> failing?")
        print("  - what happened in the last <N> ticks?")
        print("  - top-impacted")
        print("  - help | exit\n")

        query_handler = QueryHandler(simulator)

        while True:
            try:
                query = input("Query> ").strip()

                if not query:
                    continue
                if query.lower() in ['exit', 'quit', 'q']:
                    print("Goodbye!")
                    break
                if query.lower() == 'help':
                    print("\nQueries: 'why is <service> failing?', 'what happened in the last N ticks?', 'top-impacted'")
                    continue

                print(handle_query(query_handler, query))

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()
