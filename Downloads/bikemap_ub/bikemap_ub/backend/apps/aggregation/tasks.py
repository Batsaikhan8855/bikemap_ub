from .models import CrowdAggregation


def update_aggregation(segment):
    """
    Called after a Segment is saved.
    Re-counts all votes for the same spatial hash and recalculates dominant.
    — E4 US-030
    """
    from apps.segments.models import Segment as Seg

    seg_hash = CrowdAggregation.make_hash(
        segment.start_lat, segment.start_lng,
        segment.end_lat,   segment.end_lng,
    )

    # Find all segments in the same spatial cell
    nearby = Seg.objects.filter(
        start_lat__range=(float(segment.start_lat) - 0.001, float(segment.start_lat) + 0.001),
        start_lng__range=(float(segment.start_lng) - 0.001, float(segment.start_lng) + 0.001),
        end_lat__range=(float(segment.end_lat)   - 0.001, float(segment.end_lat)   + 0.001),
        end_lng__range=(float(segment.end_lng)   - 0.001, float(segment.end_lng)   + 0.001),
    )

    g = nearby.filter(condition="green").count()
    y = nearby.filter(condition="yellow").count()
    r = nearby.filter(condition="red").count()

    agg, _ = CrowdAggregation.objects.get_or_create(
        segment_hash=seg_hash,
        defaults={
            "start_lat": segment.start_lat,
            "start_lng": segment.start_lng,
            "end_lat":   segment.end_lat,
            "end_lng":   segment.end_lng,
        }
    )
    agg.green_votes  = g
    agg.yellow_votes = y
    agg.red_votes    = r
    agg.compute_dominant()
    agg.save()
    return agg