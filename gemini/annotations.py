#!/usr/bin/env python
import pysam
import os
import sys
import collections

from gemini.config import read_gemini_config

# dictionary of anno_type -> open Tabix file handles
annos = {}

# namedtuples for data returned from specific annotations
DbSnpInfo = collections.namedtuple("DbSnpInfo", 
                                   "rs_ids \
                                   in_omim \
                                   clin_sig")
ESPInfo = collections.namedtuple("ESPInfo", 
                                  "found \
                                  aaf_EA \
                                  aaf_AA \
                                  aaf_ALL \
                                  exome_chip")
ENCODESegInfo = collections.namedtuple("ENCODESegInfo", 
                                        "gm12878 \
                                         h1hesc \
                                         helas3 \
                                         hepg2 \
                                         huvec \
                                         k562")
ThousandGInfo = collections.namedtuple("ThousandGInfo", 
                                       "found \
                                        aaf_ALL \
                                        aaf_AMR \
                                        aaf_ASN \
                                        aaf_AFR \
                                        aaf_EUR")

def load_annos():
    """
    Populate a dictionary of Tabixfile handles for
    each annotation file.  Other modules can then
    access a given handle and fetch data from it
    as follows:
    
    dbsnp_handle = annotations.annos['dbsnp']
    hits = dbsnp_handle.fetch(chrom, start, end)
    """
    config = read_gemini_config()
    anno_dirname = config["annotation_dir"]
    anno_files   = {
                    'cytoband'     : \
                    os.path.join(anno_dirname, 'hg19.cytoband.bed.gz'),
                    
                    'dbsnp'        : \
                    os.path.join(anno_dirname, 'dbsnp.135.vcf.gz'),
                    
                    'gwas'         : \
                    os.path.join(anno_dirname, 'hg19.gwas.bed.gz'),
                    
                    'rmsk'         : \
                    os.path.join(anno_dirname, 'hg19.rmsk.bed.gz'),
                    
                    'segdup'       : \
                    os.path.join(anno_dirname, 'hg19.segdup.bed.gz'),
                    
                    'conserved'    : \
                    os.path.join(anno_dirname, '29way_pi_lods_elements_12mers.chr_specific.fdr_0.1_with_scores.txt.hg19.merged.bed.gz'),
                    'cpg_island'   : \
                    os.path.join(anno_dirname, 'hg19.CpG.bed.gz'),
                    
                    'dgv'          : \
                    os.path.join(anno_dirname, 'hg19.dgv.bed.gz'),
                    
                    'esp'          : \
                    os.path.join(anno_dirname, 'ESP5400.all.snps.vcf.gz'),
                    
                    '1000g'        : \
                    os.path.join(anno_dirname, 'ALL.wgs.phase1_release_v3.20101123.snps_indels_sv.sites.vcf.gz'),
                    
                    'recomb'       : \
                    os.path.join(anno_dirname, 'genetic_map_HapMapII_GRCh37.gz'),
                    
                    'gms'          : \
                    os.path.join(anno_dirname, 'GRCh37-gms-mappability.vcf.gz'),
                    
                    'grc'          : \
                    os.path.join(anno_dirname, 'GRC_patch_regions.bed.gz'),
                    
                    'encode_tfbs'  : \
                    os.path.join(anno_dirname, 'wgEncodeRegTfbsClusteredV2.cell_count.bed.gz'),
                    
                    'encode_consensus_segs'  : \
                    os.path.join(anno_dirname, \
                    'encode.6celltypes.consensus.bedg.gz'),

                    'encode_segway_segs'  : \
                    os.path.join(anno_dirname, \
                    'encode.6celltypes.segway.bedg.gz'),

                    'encode_chromhmm_segs'  : \
                    os.path.join(anno_dirname, \
                    'encode.6celltypes.chromhmm.bedg.gz')
                   }

    for anno in anno_files:
        annos[anno] = pysam.Tabixfile(anno_files[anno])


def _get_hits(var, chrom, annotation, parser_type):
    """Retrieve BED information, recovering if BED annotation file does have a chromosome.
    """
    if parser_type == "bed":
        parser = pysam.asBed()
    elif parser_type == "vcf":
        parser = pysam.asVCF()
    elif parser_type == "tuple":
        parser = pysam.asTuple()
    else:
        raise ValueError("Unexpected parser type: %s" % parser)
    try:
       hit_iter = annos[annotation].fetch(chrom, var.start, 
                                          var.end, parser=parser)
    # catch invalid region errors raised by ctabix
    except ValueError:
        hit_iter = []
    return hit_iter

def _get_chr_as_grch37(var):
    if var.CHROM in ["chrM"]:
        return "MT"
    return var.CHROM if not var.CHROM.startswith("chr") else var.CHROM[3:]
    
def _get_chr_as_ucsc(var):
    return var.CHROM if var.CHROM.startswith("chr") else "chr" + var.CHROM

def get_cpg_island_info(var):
    """
    Returns a boolean indicating whether or not the
    variant overlaps a CpG island 
    """
    chrom = _get_chr_as_ucsc(var)
    for hit in _get_hits(var, chrom, "cpg_island", "bed"):
        return True
    return False

def get_cyto_info(var):
    """
    Returns a comma-separated list of the chromosomal
    cytobands that a variant overlaps.
    """
    chrom = _get_chr_as_ucsc(var)
    cyto_band = ''
    for hit in _get_hits(var, chrom, "cytoband", "bed"):
        if len(cyto_band) > 0:
            cyto_band += "," + chrom + hit.name
        else: 
            cyto_band += chrom + hit.name
    return cyto_band if len(cyto_band) > 0 else None

def get_dbsnp_info(var):
    """
    Returns a suite of annotations from dbSNP
    """
    chrom = _get_chr_as_grch37(var)
    rs_ids  = []
    clin_sigs = []
    in_omim = 0
    for hit in _get_hits(var, chrom, "dbsnp", "vcf"):
        rs_ids.append(hit.id)
        # load each VCF INFO key/value pair into a DICT
        info_map = {}
        for info in hit.info.split(";"):
            if info.find("=") > 0:
                (key, value) = info.split("=")
                info_map[key] = value
        # is the variant in OMIM?
        if info_map['SAO'] == 0 and info_map['OM']:
            in_omim = 1
        # what is the clinical significance of the variant?
        if info_map.get('SCS') is not None:
            clin_sigs.append(info_map['SCS'])
        
    rs_str = ",".join(rs_ids) if len(rs_ids) > 0 else None
    clin_sigs_str = ",".join(clin_sigs) if len(clin_sigs) > 0 else None
    return DbSnpInfo(rs_str, in_omim, clin_sigs_str)


def get_esp_info(var):
    """
    Returns a suite of annotations from the ESP project
    """
    chrom = _get_chr_as_grch37(var)
    aaf_EA = aaf_AA = aaf_ALL = None
    maf = fetched = con = []
    exome_chip = False
    found = False
    info_map = {}
    if chrom not in ['Y']:
        for hit in _get_hits(var, chrom, "esp", "vcf"):
            fetched.append(hit)
            # We need a single ESP entry for a variant
            if fetched != None and len(fetched) == 1 and \
               hit.alt == var.ALT[0] and hit.ref == var.REF:
                found = True    
                # loads each VCF INFO key/value pair into a DICT
                for info in hit.info.split(";"):      
                    if info.find("=") > 0:
                    # splits on first occurence of '='   
                    # useful to handle valuerror: too many values to unpack (e.g (a,b) = split(",", (a,b,c,d)) for cases like
                    #SA=http://www.ncbi.nlm.nih.gov/sites/varvu?gene=4524&amp%3Brs=1801131|http://omim.org/entry/607093#0004  
                        (key, value) = info.split("=", 1)
                        info_map[key] = value
                # get the % minor allele frequencies      
                if info_map.get('MAF') is not None:
                    lines = info_map['MAF'].split(",")
                    # divide by 100 because ESP reports allele 
                    # frequencies as percentages.
                    aaf_EA = float(lines[0]) / 100.0
                    aaf_AA = float(lines[0]) / 100.0
                    aaf_ALL = float(lines[0]) / 100.0
                    
                #Is the SNP on an human exome chip?
                if info_map.get('EXOME_CHIP') is not None and \
                   info_map['EXOME_CHIP'] == "no":
                    exome_chip = 0
                elif info_map.get('EXOME_CHIP') is not None and \
                     info_map['EXOME_CHIP'] == "yes":
                    exome_chip = 1        
    return ESPInfo(found, aaf_EA, aaf_AA, aaf_ALL, exome_chip)  
        
def get_1000G_info(var):
    """
    Returns a suite of annotations from the 1000 Genomes project
    """
    chrom = _get_chr_as_grch37(var)
    fetched = []
    info_map = {}
    found = False
    for hit in _get_hits(var, chrom, "1000g", "vcf"):
        fetched.append(hit)
        # We need a single 1000G entry for a variant
        if fetched != None and len(fetched) == 1 and \
           hit.alt == var.ALT[0] and hit.ref == var.REF:
            # loads each VCF INFO key/value pair into a DICT
            found = True
            for info in hit.info.split(";"):      
                if info.find("=") > 0:
                    (key, value) = info.split("=", 1)
                    info_map[key] = value

    return ThousandGInfo(found, info_map.get('AF'), info_map.get('AMR_AF'), 
                         info_map.get('ASN_AF'), info_map.get('AFR_AF'), 
                         info_map.get('EUR_AF'))
            
def get_rmsk_info(var):
    """
    Returns a comma-separated list of annotated repeats
    that overlap a variant.  Derived from the UCSC rmsk track 
    """
    chrom = _get_chr_as_ucsc(var)
    rmsk_hits = []
    for hit in _get_hits(var, chrom, "rmsk", "bed"):
        rmsk_hits.append(hit.name)
    return ",".join(rmsk_hits) if len(rmsk_hits) > 0 else None


def get_segdup_info(var):
    """
    Returns a boolean indicating whether or not the
    variant overlaps a known segmental duplication. 
    """
    chrom = var.CHROM if var.CHROM.startswith("chr") else "chr" + var.CHROM
    for hit in _get_hits(var, chrom, "segdup", "bed"):
        return True
    return False
    
def get_conservation_info(var):
    """
    Returns a boolean indicating whether or not the
    variant overlaps a conserved region as defined
    by the 29-way mammalian conservation study.
    http://www.nature.com/nature/journal/v478/n7370/full/nature10530.html
    
    Data file provenance:
    http://www.broadinstitute.org/ftp/pub/assemblies/mammals/29mammals/ \
    29way_pi_lods_elements_12mers.chr_specific.fdr_0.1_with_scores.txt.gz
    
    # Script to convert for gemini:
    gemini/annotation_provenance/make-29way-conservation.sh
    """
    chrom = _get_chr_as_ucsc(var)
    for hit in _get_hits(var, chrom, "conserved", "bed"):
        return True
    return False

def get_recomb_info(var):
    """
    Returns the mean recombination rate at the site.
    """
    chrom = _get_chr_as_ucsc(var)
    count = 0
    tot_rate = 0.0
    if chrom not in ['chrY']:
        # recomb rate file is in bedgraph format.
        # pysam will store the rate in the "name" field
        for hit in _get_hits(var, chrom, "recomb", "bed"):
            count += 1
            tot_rate += float(hit.name)

    return float(tot_rate) / float(count) if count > 0 else None

def _get_single_vcf_hit(var, hit_iter):
    if hit_iter is not None:
        hits = list(hit_iter)
        if len(hits) == 1:
            return hits[0]

def _get_vcf_info_attrs(hit):
    info_map = {}
    for info in hit.info.split(";"):      
        if info.find("=") > 0:
            (key, value) = info.split("=", 1)
            info_map[key] = value
    return info_map

def get_gms(var):
    """Return Genome Mappability Scores for multiple technologies.
    """
    techs = ["illumina", "solid", "iontorrent"]
    GmsTechs = collections.namedtuple("GmsTechs", techs)
    chrom = _get_chr_as_grch37(var)
    hit = _get_single_vcf_hit(var, _get_hits(var, chrom, "gms", "vcf"))
    attr_map = _get_vcf_info_attrs(hit) if hit is not None else {}
    return apply(GmsTechs,
                 [attr_map.get("GMS_{0}".format(x), None) for x in techs])

def get_grc(var):
    """Return GRC patched genome regions.
    """
    chrom = _get_chr_as_grch37(var)
    regions = set()
    for hit in _get_hits(var, chrom, "grc", "bed"):
        regions.add(hit.name)
    return ",".join(sorted(list(regions))) if len(regions) > 0 else None

def get_encode_tfbs(var):
    """
    Returns a comma-separated list of transcription factors that were
    observed to bind DNA in this region.  Each hit in the list is constructed
    as TF_MAXSCORE_CELLCOUNT, where:
      TF is the transcription factor name
      MAXSCORE is the highest signal strength observed in any of the cell lines
      CELLCOUNT is the number of cells tested that had nonzero signals 

    NOTE: the annotation file is in BED format, but pysam doesn't
    tolerate BED files with more than 12 fields, so we just use the base
    tuple parser and grab the name column (4th column)
    """
    chrom = _get_chr_as_ucsc(var)
    encode_tfbs_hits = []

    for hit in _get_hits(var, chrom, "encode_tfbs", "tuple"):
        encode_tfbs_hits.append(hit[3])
    return ",".join(encode_tfbs_hits) if len(encode_tfbs_hits) > 0 else None

def get_encode_consensus_segs(var):
    """
    Queries a meta-BEDGRAPH of consensus ENCODE segmentations for 6 cell types:
    gm12878, h1hesc, helas3, hepg2, huvec, k562
    
    Returns a 6-tuple of the predicted chromatin state of each cell type for the
    region overlapping the variant.
    
    CTCF: CTCF-enriched element
    E:    Predicted enhancer
    PF:   Predicted promoter flanking region
    R:    Predicted repressed or low-activity region
    TSS:  Predicted promoter region including TSS
    T:    Predicted transcribed region
    WE:   Predicted weak enhancer or open chromatin cis-regulatory element
    """
    chrom = _get_chr_as_ucsc(var)
    for hit in _get_hits(var, chrom, "encode_consensus_segs", "tuple"):
        return ENCODESegInfo(hit[3], hit[4], hit[5], hit[6], hit[7], hit[8])
    
    return ENCODESegInfo(None, None, None, None, None, None)

def get_encode_segway_segs(var):
    """
    Queries a meta-BEDGRAPH of SegWay ENCODE segmentations for 6 cell types:
    gm12878, h1hesc, helas3, hepg2, huvec, k562
    
    Returns a 6-tuple of the predicted chromatin state of each cell type for the
    region overlapping the variant.
    """
    chrom = _get_chr_as_ucsc(var)
    for hit in _get_hits(var, chrom, "encode_segway_segs", "tuple"):
        return ENCODESegInfo(hit[3], hit[4], hit[5], hit[6], hit[7], hit[8])
    
    return ENCODESegInfo(None, None, None, None, None, None)
    
def get_encode_chromhmm_segs(var):
    """
    Queries a meta-BEDGRAPH of SegWay ENCODE segmentations for 6 cell types:
    gm12878, h1hesc, helas3, hepg2, huvec, k562
    
    Returns a 6-tuple of the predicted chromatin state of each cell type for the
    region overlapping the variant.
    """
    chrom = _get_chr_as_ucsc(var)
    for hit in _get_hits(var, chrom, "encode_chromhmm_segs", "tuple"):
        return ENCODESegInfo(hit[3], hit[4], hit[5], hit[6], hit[7], hit[8])
    
    return ENCODESegInfo(None, None, None, None, None, None)
