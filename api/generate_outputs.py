import io
import json
import pandas as pd
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio import SeqIO
from bgc_data_portal import __description__,__name__,__version__

class WriteRegion:
    @staticmethod
    def gbk(contig, start_position: int, end_position: int, assembly_accession: str, region_df: pd.DataFrame):
        """
        Write the region data to GenBank format using the provided DataFrame.

        Args:
            region_df (pd.DataFrame): DataFrame containing region features.
            mgyc (str): Contig name.
            start_position (int): Start position.
            end_position (int): End position.
            assembly_accession (str): Assembly accession.

        Returns:
            str: GenBank data as a string.
        """
        mgyc= contig.mgyc
        contig_seq = Seq(contig.sequence[start_position-1:end_position])
        description = (
            f"Nucleotide sequence extracted from "
            f"Assembly: {assembly_accession}, "
            f"Contig: {mgyc}, "
            f"Region: {start_position}-{end_position}, "
            f"Generated using {__name__} version {__version__}."
        )
        record = SeqRecord(
            contig_seq,
            id=f"{mgyc}:{start_position}-{end_position}",
            description=description,
            annotations={"molecule_type": "DNA"}
        )

        for _, row in region_df.iterrows():
            if row['type'] == 'CLUSTER':


                feature = SeqFeature(
                    location=FeatureLocation(
                        max(row['start'], start_position),
                        min(row['end'], end_position)
                    ),
                    type=row['type'],
                    qualifiers={
                        "ID": row['attrib'].get('ID'),
                        "bgc_class": row['attrib'].get('BGC_CLASS') if pd.notna(row['attrib'].get('BGC_CLASS')) else "Unknown",
                        "bgc_detector": row['source'] if pd.notna(row['source']) else "Unknown",
                    }
                )
                record.features.append(feature)

            if row['type'] == 'CDS':
                protein = row['attrib']
                feature = SeqFeature(
                    location=FeatureLocation(
                        max(row['start'], start_position),
                        min(row['end'], end_position),
                        strand=row['strand']),
                    type="CDS",
                    qualifiers={
                        "protein_id": protein['mgyp'],
                        "translation": protein['sequence'],
                        "pfam": protein['pfam'],
                    }
                )
                record.features.append(feature)

            if row['type'] == 'ANNOT':
                protein = row['attrib']
                feature = SeqFeature(
                    location=FeatureLocation(
                        max(row['start'], start_position),
                        min(row['end'], end_position),
                        strand=row['strand']),
                    type=row['type'],
                    qualifiers={
                        "ID": protein['ID'],
                        "source": row['source'],
                        "description": protein['description'],
                    }
                )
                record.features.append(feature)

        genbank_io = io.StringIO()
        SeqIO.write(record, genbank_io, "genbank")
        genbank_data = genbank_io.getvalue()
        genbank_io.close()

        return genbank_data

    @staticmethod
    def json(contig, start_position: int, end_position: int, assembly_accession: str, region_df: pd.DataFrame):
        """
        Generate output following the antiSMASH JSON format for sideloading.

        Args:
            region_df (pd.DataFrame): DataFrame containing region features.
            mgyc (str): Contig name.
            start_position (int): Start position.
            end_position (int): End position.
            assembly_accession (str): Assembly accession.

        Returns:
            str: JSON data as a string.
        """
        mgyc= contig.mgyc
        tool_info = {
            "name": __name__,
            "version": __version__,
            "description": f"{__description__} This subregion was created using the portal module to generate JSON files for antiSMASH sideloading.",
        }

        contig_description = (
            f"Nucleotide sequence extracted from "
            f"Assembly: {assembly_accession}, "
            f"Contig: {mgyc}, "
            f"Region: {start_position}-{end_position}, "
            f"Generated using {__name__} version {__version__}."
        )

        details = {'Detected BGCs': [], 'Sequence description': contig_description}
        for _, row in region_df.iterrows():
            if row['type'] == 'CLUSTER':
                mgyb = row['mgyb']
                detector = row['source'] if pd.notna(row['source']) else "Unknown"
                detector_version = row['attrib'].get('detector_version', "Unknown")
                bgc_class = row['attrib'].get('BGC_CLASS') if pd.notna(row['attrib'].get('BGC_CLASS')) else "Unknown"
                start_position_str = str(max(row['start'], start_position))
                end_position_str = str(min(row['end'], end_position))
                details["Detected BGCs"].append(
                    f"Accession: {mgyb};Start {start_position_str}; End: {end_position_str}; Detector: {detector}v{detector_version};Class: {bgc_class}; "
                )

        subregion = {
            "start": start_position,
            "end": end_position,
            "label": f"{mgyc}:{start_position}-{end_position}",
            "details": details
        }

        record_info = {
            "name": mgyc,
            "subregions": [subregion],
            "protoclusters": []
        }

        output_data = {
            "tool": tool_info,
            "record": record_info
        }

        return json.dumps(output_data, indent=4)

    @staticmethod
    def fasta(contig, start_position: int, end_position: int, assembly_accession: str, region_df: pd.DataFrame):
        """
        Generate the region sequence in FASTA format.

        Args:
            region_df (pd.DataFrame): DataFrame containing region features.
            mgyc (str): Contig name.
            start_position (int): Start position.
            end_position (int): End position.
            assembly_accession (str): Assembly accession.

        Returns:
            str: FASTA formatted string of the sequence region.
        """
        mgyc= contig.mgyc
        contig_seq = Seq(contig.sequence[start_position-1:end_position])

        description = (
            f"Nucleotide sequence extracted from "
            f"Assembly: {assembly_accession}, "
            f"Contig: {mgyc}, "
            f"Region: {start_position}-{end_position}, "
            f"Generated using {__name__} version {__version__}."
        )

        seq_record = SeqRecord(
            Seq(contig_seq),
            id=f"{mgyc}:{start_position}-{end_position}",
            description=description
        )

        fasta_io = io.StringIO()
        SeqIO.write(seq_record, fasta_io, "fasta")
        fasta_data = fasta_io.getvalue()
        fasta_io.close()

        return fasta_data
