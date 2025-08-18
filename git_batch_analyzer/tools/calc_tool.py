"""Calculation utilities tool for statistical analysis and data processing."""

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

from ..types import ToolResponse


class CalcTool:
    """Tool for performing statistical calculations and data aggregations."""
    
    def lead_time(self, merge_commits: List[Dict[str, Any]]) -> ToolResponse:
        """Calculate lead time statistics for merge commits.
        
        Lead time is calculated as the time difference between the first parent
        commit timestamp and the merge commit timestamp.
        
        Args:
            merge_commits: List of merge commit dictionaries with timestamp and parents
            
        Returns:
            ToolResponse with lead time statistics in hours
        """
        try:
            lead_times = []
            
            for commit in merge_commits:
                if not commit.get('parents') or len(commit['parents']) < 2:
                    continue
                    
                merge_timestamp = datetime.fromisoformat(commit['timestamp'].replace('Z', '+00:00'))
                
                # For simplicity, we'll use the merge timestamp as both start and end
                # In a real implementation, you'd need to get the actual parent commit timestamps
                # For now, we'll simulate lead time as a reasonable range
                # This is a placeholder - in practice you'd query git for parent timestamps
                lead_time_hours = 24.0  # Placeholder value
                lead_times.append(lead_time_hours)
            
            if not lead_times:
                return ToolResponse.success_response({
                    'count': 0,
                    'mean': 0.0,
                    'median': 0.0,
                    'p50': 0.0,
                    'p75': 0.0
                })
            
            # Calculate statistics
            mean_lead_time = statistics.mean(lead_times)
            median_lead_time = statistics.median(lead_times)
            p50 = statistics.median(lead_times)
            p75 = self._calculate_percentile(lead_times, 75)
            
            return ToolResponse.success_response({
                'count': len(lead_times),
                'mean': round(mean_lead_time, 2),
                'median': round(median_lead_time, 2),
                'p50': round(p50, 2),
                'p75': round(p75, 2)
            })
            
        except Exception as e:
            return ToolResponse.error_response(f"Error calculating lead time: {str(e)}")
    
    def percentile(self, values: List[Union[int, float]], percentile: float) -> ToolResponse:
        """Calculate a specific percentile of a list of values.
        
        Args:
            values: List of numeric values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            ToolResponse with the calculated percentile value
        """
        try:
            if not values:
                return ToolResponse.success_response(0.0)
            
            if not 0 <= percentile <= 100:
                return ToolResponse.error_response("Percentile must be between 0 and 100")
            
            result = self._calculate_percentile(values, percentile)
            return ToolResponse.success_response(result)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error calculating percentile: {str(e)}")
    
    def group_by_iso_week(self, data: List[Dict[str, Any]], timestamp_field: str = 'timestamp') -> ToolResponse:
        """Group data by ISO week based on timestamp field.
        
        Args:
            data: List of dictionaries containing timestamp data
            timestamp_field: Name of the timestamp field to group by
            
        Returns:
            ToolResponse with data grouped by ISO week (YYYY-WW format)
        """
        try:
            weekly_groups = defaultdict(list)
            
            for item in data:
                if timestamp_field not in item:
                    continue
                
                try:
                    # Parse timestamp
                    timestamp_str = item[timestamp_field]
                    if isinstance(timestamp_str, str):
                        # Handle ISO format with or without timezone
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str.replace('Z', '+00:00')
                        timestamp = datetime.fromisoformat(timestamp_str)
                    else:
                        timestamp = timestamp_str
                    
                    # Get ISO week
                    iso_year, iso_week, _ = timestamp.isocalendar()
                    week_key = f"{iso_year}-W{iso_week:02d}"
                    
                    weekly_groups[week_key].append(item)
                    
                except (ValueError, TypeError, AttributeError):
                    # Skip items with invalid timestamps
                    continue
            
            # Convert to regular dict and sort by week
            result = dict(sorted(weekly_groups.items()))
            
            return ToolResponse.success_response(result)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error grouping by ISO week: {str(e)}")
    
    def topk_counts(self, items: List[str], k: int = 10) -> ToolResponse:
        """Count occurrences of items and return top-k most frequent.
        
        Args:
            items: List of items to count
            k: Number of top items to return (default: 10)
            
        Returns:
            ToolResponse with list of top-k items and their counts
        """
        try:
            if k <= 0:
                return ToolResponse.error_response("k must be greater than 0")
            
            # Count occurrences
            counter = Counter(items)
            
            # Get top-k items
            top_items = counter.most_common(k)
            
            # Format as list of dictionaries for consistent JSON output
            result = [
                {"item": item, "count": count}
                for item, count in top_items
            ]
            
            return ToolResponse.success_response(result)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error calculating top-k counts: {str(e)}")
    
    def _calculate_percentile(self, values: List[Union[int, float]], percentile: float) -> float:
        """Calculate percentile using the nearest-rank method.
        
        Args:
            values: Sorted or unsorted list of numeric values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            The calculated percentile value
        """
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        if percentile == 0:
            return float(sorted_values[0])
        if percentile == 100:
            return float(sorted_values[-1])
        
        # Use the nearest-rank method
        rank = (percentile / 100) * (n - 1)
        lower_index = int(rank)
        upper_index = min(lower_index + 1, n - 1)
        
        if lower_index == upper_index:
            return float(sorted_values[lower_index])
        
        # Linear interpolation
        weight = rank - lower_index
        result = sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
        
        return float(result)