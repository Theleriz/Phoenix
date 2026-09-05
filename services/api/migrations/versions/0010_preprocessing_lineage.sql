-- Stage 8: preprocessing outputs are immutable and traceable to source chunks.

CREATE TRIGGER derived_metrics_immutable
    BEFORE UPDATE OR DELETE ON derived_metrics
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();

CREATE TRIGGER signal_quality_immutable
    BEFORE UPDATE OR DELETE ON signal_quality
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();

CREATE TRIGGER calibrations_immutable
    BEFORE UPDATE OR DELETE ON calibrations
    FOR EACH ROW EXECUTE FUNCTION prevent_immutable_change();
