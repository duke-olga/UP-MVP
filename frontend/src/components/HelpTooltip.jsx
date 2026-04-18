export default function HelpTooltip({ text }) {
  return (
    <span className="help-tooltip" title={text} aria-label={text}>
      ?
    </span>
  );
}
