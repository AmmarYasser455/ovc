/* The OVC Toolbox: the tools shown in the Geoprocessing pane.
 *
 * To add a tool, add an entry to a toolset below (or a new toolset). The
 * pane builds the tool's form from `params`, and `request(values)` turns the
 * filled-in values into the options sent to the OVC engine (/api/scan, the
 * same engine as `ovc check` and ovc.check_file()). See CONTRIBUTING.md,
 * "Adding a tool to the OVC Toolbox".
 *
 * Parameter types:
 *   layer   a layer from Contents. `geometry: "polygon"` limits the choice.
 *   field   an attribute of the layer named in `of`.
 *   crs     shown only when the layer named in `of` has no CRS.
 *   number  with `min`, `step`, `default`.
 *   bool    a checkbox, with `default`.
 * Every parameter has a `label` and a one-sentence `help` shown under it.
 */
window.OVC_TOOLBOX = {
  name: "OVC Toolbox",
  toolsets: [
    {
      name: "Topology",
      tools: [
        {
          id: "find-overlaps",
          name: "Find Overlaps",
          summary:
            "Finds every pair of features in a polygon layer that share area, including identical (duplicate) features and features inside another. Features that only share an edge or a corner are not overlaps.",
          params: [
            { name: "input", label: "Input Features", type: "layer", geometry: "polygon", required: true,
              help: "The polygon layer to check. It is read only; the file is never changed." },
            { name: "assume_crs", label: "Coordinate System of Input", type: "crs", of: "input",
              help: "The layer has no CRS. Enter the EPSG code its coordinates are in. OVC never guesses one." },
            { name: "id_field", label: "ID Field", type: "field", of: "input",
              help: "Optional. Findings always carry the feature ID (FID); pick a field to show your own ID as well." },
            { name: "min_overlap_area_m2", label: "Minimum Overlap Area (m²)", type: "number", min: 0, step: 0.01, default: 0.01,
              help: "Overlaps smaller than this are not reported. An overlap equal to it is. 0 reports every overlap with any area." },
            { name: "repair_invalid", label: "Repair invalid geometries in memory", type: "bool", default: false,
              help: "Off: invalid polygons are reported and skipped. On: they are repaired for this run and checked." },
          ],
          request: (v) => ({
            check_overlaps: true,
            check_gaps: false,
            id_field: v.id_field,
            assume_crs: v.assume_crs,
            min_overlap_area_m2: v.min_overlap_area_m2,
            repair_invalid: v.repair_invalid,
          }),
        },
        {
          id: "find-gaps",
          name: "Find Gaps",
          summary:
            "Finds the parts of a coverage area that no feature covers, such as slivers between parcels in a block. Each connected gap is reported with its area. Needs a polygon layer of the area that should be fully covered; OVC never guesses that area.",
          params: [
            { name: "input", label: "Input Features", type: "layer", geometry: "polygon", required: true,
              help: "The polygon layer that should cover the area, for example parcels." },
            { name: "assume_crs", label: "Coordinate System of Input", type: "crs", of: "input",
              help: "The layer has no CRS. Enter the EPSG code its coordinates are in. OVC never guesses one." },
            { name: "coverage", label: "Coverage Area", type: "layer", geometry: "polygon", required: true, distinctFrom: "input",
              help: "The area that should be fully covered, such as a parcel block. Holes in it are not expected to be covered." },
            { name: "id_field", label: "ID Field", type: "field", of: "input",
              help: "Optional. Your own feature ID, shown with the FIDs of the features next to each gap." },
            { name: "min_gap_area_m2", label: "Minimum Gap Area (m²)", type: "number", min: 0, step: 0.01, default: 0.01,
              help: "Gaps smaller than this are not reported. A gap equal to it is." },
            { name: "also_overlaps", label: "Also find overlaps", type: "bool", default: true,
              help: "Report overlapping features in the same run." },
            { name: "repair_invalid", label: "Repair invalid geometries in memory", type: "bool", default: false,
              help: "Off: invalid polygons are skipped and gaps near them are marked unreliable. On: they are repaired for this run." },
          ],
          request: (v) => ({
            check_overlaps: v.also_overlaps,
            check_gaps: true,
            coverage: v.coverage,
            id_field: v.id_field,
            assume_crs: v.assume_crs,
            min_gap_area_m2: v.min_gap_area_m2,
            repair_invalid: v.repair_invalid,
          }),
        },
      ],
    },
  ],
};
