"""Correlation validation for future authenticated peer exchange."""
class ExperimentSynchronizer:
    @staticmethod
    def correlation_key(experiment_uuid,measurement):
        # Positional row matching and wall-clock matching alone are forbidden.
        return (experiment_uuid,measurement['session_id'],measurement['stage_id'],measurement.get('interval_start'),measurement.get('seconds'))
    @staticmethod
    def validate_peer_result(local_uuid,remote):
        if remote.get('experiment_uuid')!=local_uuid:
            raise ValueError('Peer experiment UUID mismatch')
        if not remote.get('session_id'):raise ValueError('Peer session ID required')
        return remote
