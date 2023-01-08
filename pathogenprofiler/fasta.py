from collections import OrderedDict
from .utils import run_cmd, cmd_out, debug
from uuid import uuid4
from .kmer import kmer_dump
import os
import platform 

class fasta:
    """
    Class to represent fasta seuqnces in a python dict.

    Args:
        filename(str): Location of the fasta file

    Returns:
        fasta: A fasta class object
    """
    def __init__(self,filename):
        fa_dict = OrderedDict()
        seq_name = ""
        self.fa_file = filename
        for l in open(filename):
            line = l.rstrip()
            if line=="": continue
            if line.startswith(">"):
                seq_name = line[1:].split()[0]
                fa_dict[seq_name] = []
            else:
                fa_dict[seq_name].append(line)
        result = {}
        counter = 0
        sum_length = {}
        for seq in fa_dict:
            result[seq] = "".join(fa_dict[seq])
            result[seq] = result[seq].upper()
            sum_length[(counter+1,counter+len(result[seq]))] = seq
            counter = counter+len(result[seq])
        self.sum_length = sum_length
        self.fa_dict = result
    def get_ref_variants(self,refseq,prefix,file_prefix=None):
        self.refseq = refseq
        self.prefix = prefix
        self.file_prefix = file_prefix
        if self.file_prefix==None:
            self.file_prefix=prefix
        if "ref_aln" not in vars(self):
            self.align_to_ref(refseq,self.file_prefix)
        run_cmd("cat %(ref_aln)s | paftools.js call -l 100 -L 100 -f %(refseq)s -s %(prefix)s - | add_dummy_AD.py | bcftools view -Oz -o %(file_prefix)s.vcf.gz" % vars(self))
        return "%s.vcf.gz" % self.file_prefix
    def align_to_ref(self,refseq,file_prefix):
        self.ref_aln = f"{file_prefix}.paf"
        run_cmd(f"minimap2 {refseq} {self.fa_file} --cs | sort -k6,6 -k8,8n > {self.ref_aln}")
    def get_aln_coverage(self,bed):
        results = []
        for l in cmd_out(f"cut -f6,8,9 {self.ref_aln} | bedtools coverage -a {bed} -b -"):
            row = l.strip().split()
            results.append({"gene_id":row[3],"gene_name":row[4],"cutoff":1,"fraction":1-float(row[9])})
        return results
    def get_amplicons(self,primer_file):
        bed = []
        for l in cmd_out(f"seqkit amplicon {self.fa_file} -p {primer_file} --bed"):
            row = l.strip().split()
            bed.append(tuple(row[:4]))
            
        return bed
    def get_kmer_counts(self,prefix,klen = 31,threads=1,max_mem=2, counter = "kmc"):
        if counter=="kmc":
            if threads>32:
                threads = 32
            tmp_prefix = f"{prefix}_kmers"
            os.mkdir(tmp_prefix)
            bins = "-n128" if platform.system()=="Darwin" else ""
            run_cmd(f"kmc {bins} -m{max_mem} -t{threads} -k{klen} -ci1 -fm  {self.fa_file} {tmp_prefix} {tmp_prefix}")
            run_cmd(f"kmc_dump -ci1 {tmp_prefix} {tmp_prefix}.kmers.txt")
            os.rename(f"{tmp_prefix}.kmers.txt", f"{prefix}.kmers.txt")
            run_cmd(f"rm -r {tmp_prefix}*")

            return kmer_dump(f"{prefix}.kmers.txt",counter)
        elif counter=="dsk":
            max_mem = max_mem * 1000
            tmp_prefix = f"{prefix}_kmers"
            os.mkdir(tmp_prefix)
            run_cmd(f"dsk -file {self.fa_file} -abundance-min 1 -nb-cores {threads} -kmer-size {klen} -max-memory {max_mem} -out {tmp_prefix} -out-tmp {tmp_prefix}")
            run_cmd(f"dsk2ascii -file {tmp_prefix}.h5 -out {tmp_prefix}.kmers.txt")
            os.rename(f"{tmp_prefix}.kmers.txt", f"{prefix}.kmers.txt")
            run_cmd(f"rm -r {tmp_prefix}*")

            return kmer_dump(f"{prefix}.kmers.txt",counter)