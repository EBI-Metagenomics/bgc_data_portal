def smiles_to_svg(smiles: str, size: tuple[int, int] = (200, 200)) -> str:
    """
    Given a SMILES string, return an SVG string of its 2D depiction.
    If RDKit cannot parse, returns an empty string.
    We strip out the XML header so you can embed directly in HTML.
    """
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    # Compute 2D coords if not already present
    Chem.rdDepictor.Compute2DCoords(mol)
    drawer = rdMolDraw2D.MolDraw2DSVG(size[0], size[1])
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol)
    drawer.FinishDrawing()
    svg = drawer.GetDrawingText()
    # Remove XML header so it can be embedded directly in the template
    svg = svg.replace("<?xml version='1.0' encoding='UTF-8'?>", "").strip()
    return svg
