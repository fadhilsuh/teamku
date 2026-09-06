export function PageSkeleton(){
  return <div className="page-skeleton" role="status" aria-label="Memuat halaman">
    <div className="skeleton-heading"><span className="skeleton skeleton-eyebrow"/><span className="skeleton skeleton-title"/><span className="skeleton skeleton-copy"/></div>
    <div className="skeleton-metrics">{Array.from({length:4},(_,index)=><div className="skeleton-card" key={index}><span className="skeleton skeleton-icon"/><span className="skeleton skeleton-label"/><span className="skeleton skeleton-value"/></div>)}</div>
    <div className="skeleton-panels"><div className="skeleton-panel"><span className="skeleton skeleton-title short"/><span className="skeleton skeleton-row"/><span className="skeleton skeleton-row"/><span className="skeleton skeleton-row narrow"/></div><div className="skeleton-panel"><span className="skeleton skeleton-title short"/><span className="skeleton skeleton-row"/><span className="skeleton skeleton-row"/><span className="skeleton skeleton-row narrow"/></div></div>
  </div>;
}
