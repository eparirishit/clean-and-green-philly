import warnings
from typing import Tuple

import geopandas as gpd
import networkx as nx
import numpy as np
from libpysal.weights import Queen

from src.validation.base import ValidationResult, validate_output
from src.validation.contig_neighbors import ContigNeighborsOutputValidator

from ..utilities import opa_join


@validate_output(ContigNeighborsOutputValidator)
def contig_neighbors(
    input_gdf: gpd.GeoDataFrame,
) -> Tuple[gpd.GeoDataFrame, ValidationResult]:
    """
    Calculates the number of contiguous vacant neighbors for each property in a feature layer.

    Args:
        primary_featurelayer (FeatureLayer): A feature layer containing property data in a GeoDataFrame (`gdf`).

    Returns:
        FeatureLayer: The input feature layer with an added "n_contiguous" column indicating
        the number of contiguous vacant neighbors for each property.

    Tagline:
        Count vacant neighbors

    Columns Added:
        n_contiguous (int): The number of contiguous vacant neighbors for each property.

    Primary Feature Layer Columns Referenced:
        opa_id, vacant
    """
    # Create a filtered dataframe with only vacant properties and polygon geometries
    vacant_parcels = input_gdf.loc[
        (input_gdf["vacant"])
        & (input_gdf.geometry.type.isin(["Polygon", "MultiPolygon"])),
        ["opa_id", "geometry"],
    ]

    if vacant_parcels.empty:
        print("No vacant properties found in the dataset.")
        input_gdf["n_contiguous"] = np.nan
        return input_gdf

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        warnings.filterwarnings(
            "ignore",
            category=UserWarning,
            message="The weights matrix is not fully connected",
        )

        # Create a spatial weights matrix for vacant parcels
        w = Queen.from_dataframe(vacant_parcels)

    # Convert the spatial weights matrix to a NetworkX graph
    g = w.to_networkx()

    # Calculate the number of contiguous vacant properties for each vacant parcel
    n_contiguous = {
        node: len(nx.node_connected_component(g, node)) - 1 for node in g.nodes
    }

    # Assign the contiguous neighbor count to the filtered vacant parcels
    vacant_parcels["n_contiguous"] = vacant_parcels.index.map(n_contiguous)

    # Merge the results back to the primary feature layer
    input_gdf = opa_join(input_gdf, vacant_parcels[["opa_id", "n_contiguous"]])

    # Assign NA for non-vacant properties
    input_gdf.loc[~input_gdf["vacant"], "n_contiguous"] = np.nan

    return input_gdf, ValidationResult(True)
