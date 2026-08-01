import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { fetchHealth } from "../api/health";
import { HealthStatus } from "../components/HealthStatus";

export function HomePage(): JSX.Element {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
  });

  return (
    <main className="page-shell">
      <section className="hero" aria-labelledby="project-title">
        <p className="eyebrow">工程基线</p>
        <h1 id="project-title">Career Planning Buddy</h1>
        <p className="intro">职业规划伙伴正在准备与你一起把方向变成下一步行动。</p>
        <HealthStatus
          health={healthQuery.data}
          isError={healthQuery.isError}
          isPending={healthQuery.isPending}
        />
        <p><Link to="/dev/runs">Open developer Trace console</Link></p>
      </section>
    </main>
  );
}
