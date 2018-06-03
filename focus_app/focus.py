# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import logging
import os
import random
import sys

from pathlib import Path
from collections import defaultdict

from numpy import array
from numpy import sum as numpy_sum
from scipy.optimize import nnls


LOGGER_FORMAT = '[%(asctime)s - %(levelname)s] %(message)s'
logging.basicConfig(format=LOGGER_FORMAT, level=logging.INFO)
LOGGER = logging.getLogger(__name__)

WORK_DIRECTORY = 'focus_app'


def normalise(raw_counts):
    """Normalise raw counts into proportions.

    Args:
        raw_counts (numpy.ndarray): array with raw count

    Returns:
        numpy.ndarray: Normalised data

    """
    return raw_counts / (numpy_sum(raw_counts) * 1.)


def load_database(database_path):
    """Load database.

    Args:
        database_path (PosixPath): Path to database

    Returns:
        numpy.ndarray: matrix with loaded database
        list: list of organisms in the database

    """
    database_results = {}
    with open(database_path) as database_file:
        database_reader = csv.reader(database_file, delimiter='\t')
        next(database_reader, None)
        for row in database_reader:
            if '0' in row[9] and numpy_sum(array(row[8:], dtype='i')) == 0:
                sys.stderr.write("There are no kmers found for " + "\t".join(row[:8]))
                continue
            database_results["\t".join(row[:8])] = normalise(array(row[8:], dtype='i'))

    organisms = list(database_results.keys())
    database_results = array([database_results[organism] for organism in organisms])

    return database_results.T, organisms


def count_kmers(kmer_size, method="jellyfish"):
    """Count k-mers on FAST(A/Q) file.

    Args:
        kmer_size (str): k-mer size
        method (str): software to count k-mers

    Returns:
        numpy.ndarray: raw count of k-mers

    """
    pass


def count_kmers_fake(kmer_size, method="jellyfish"):
    """Count k-mers on FAST(A/Q) file.

    Args:
        kmer_size (str): k-mer size
        method (str): software to count k-mers

    Returns:
        numpy.ndarray: raw count of k-mers

    """
    return normalise([random.randint(10000, 200000) for _ in range(2080)])


def write_results(results, output_directory, query_files, taxonomy_level):
    """Write FOCUS results.

     Args:
         results (dict): Profile for all the metagenomes
         output_directory (PosixPath): Path to output file
         query_files (list): List with list of files profiled
         taxonomy_level (list): Taxonomy level(s)

     """
    with open(output_directory, 'w') as outfile:
        writer = csv.writer(outfile, delimiter='\t', lineterminator='\n')

        writer.writerow(taxonomy_level + [targeted_file for targeted_file in query_files])

        for taxa in results:
            if sum(results[taxa]) > 0:
                writer.writerow(taxa.split("\t") + [abundance * 100 for abundance in results[taxa]])


def aggregate_level(results, position):
    """Aggregate abundance of metagenomes by taxonomic level.

    Args:
        results (dict): Path to database
        position (int): Position of level in the results

    Returns:
        dict: Aggregated result targeting chosen level

    """
    level_results = defaultdict(list)

    for all_taxa in results:
        taxa = all_taxa.split("\t")[position]
        abundance = results[all_taxa]
        level_results[taxa].append(abundance)

    return {temp_taxa: numpy_sum(level_results[temp_taxa], axis=0) for temp_taxa in level_results}


def run_nnls(database_matrix, query_count):
    """Run Non-negative least squares (NNLS) algorithm.

    Args:
        database_matrix (numpy.ndarray): Matrix with count for organisms in the database
        query_count (numpy.ndarray): Metagenome k-mer count

    Returns:
        numpy.ndarray: Abundances of each organism

    """
    return normalise(nnls(database_matrix, query_count)[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-q", "--query", help="Path to FAST(A/Q) file or directory with these files", required=True)
    parser.add_argument("-o", "--output_directory",  help="Path to output files", required=True)
    parser.add_argument("-k", "--kmer_size",  help="K-mer size (6 or 7)", default="6")
    parser.add_argument("-d", "--work_directory",  help="Work directory", default="focus_app")
    parser.add_argument("-b", "--alternate_directory",  help="Alternate directory for your databases", default="")
    parser.add_argument("-p", "--output_prefix",  help="Output prefix", default="output")

    args = parser.parse_args()

    query = Path(args.query)
    prefix = args.output_prefix
    output_directory = Path(args.output_directory)
    kmer_size = args.kmer_size
    WORK_DIRECTORY = Path(args.alternate_directory) if args.alternate_directory else Path(args.work_directory)
    database_path = Path(WORK_DIRECTORY, "db/k" + kmer_size)

    # check if query is exists
    if not query.exists():
        LOGGER.critical("QUERY: {} does not exist".format(query))

    # check if output_directory is exists
    elif not output_directory.exists():
        LOGGER.critical("OUTPUT: {} does not exist".format(output_directory))

    # check if database exists
    elif not database_path.exists():
        LOGGER.critical("DATABASE: {} does not exist. Did you extract db.zip?".format(database_path))

    # check if work directory exists
    elif WORK_DIRECTORY != WORK_DIRECTORY or not WORK_DIRECTORY.exists():
        LOGGER.critical("WORK_DIRECTORY: {} does not exist".format(WORK_DIRECTORY))

    # check k-mer size
    elif kmer_size not in ["6", "7"]:
        LOGGER.critical("K-MER SIZE: {} is not a valid k-mer size for this program - "
                        "please choose 6 or 7".format(kmer_size))

    else:
        LOGGER.info("FOCUS: An Agile Profiler for Metagenomic Data")
        LOGGER.info("1) Loading Reference DB")
        database_path = Path(WORK_DIRECTORY, "db/k" + kmer_size)
        database_matrix, organisms = load_database(database_path)

        LOGGER.info("2) Reference DB was loaded with {} reference genomes".format(len(organisms)))
        # get fasta/fastq files
        query_files = [query] if query.is_file() else [temp_query for temp_query in os.listdir(query)]
        query_files.sort()

        results = {taxa: [0] * len(query_files) for taxa in organisms}

        counter = 1
        for temp_query in query_files:
            LOGGER.info("3.{}) Working on: {}".format(counter, temp_query))

            LOGGER.info("   Counting k-mers")
            query_count = count_kmers_fake(kmer_size)
            # find the best set of organisms that reconstruct the user metagenome using NNLS
            LOGGER.info("   Running FOCUS")
            organisms_abundance = run_nnls(database_matrix, query_count)

            # store results
            query_index = query_files.index(temp_query)
            for pos in range(len(organisms)):
                results[organisms[pos]][query_index] = organisms_abundance[pos]

            counter += 1

        LOGGER.info('5) Writing Results to {}'.format(output_directory))
        taxomy_levels = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species", "Strain"]

        # All taxonomy levels in one output
        output_file = Path(output_directory, prefix + "_All_levels.xls")
        write_results(results, output_file, query_files, taxomy_levels)

        # write output for each taxonomy level
        for pos, level in enumerate(taxomy_levels):
            LOGGER.info('  5.{}) Working on {}'.format(pos + 1, level))
            level_result = aggregate_level(results, pos)
            output_file = Path(output_directory, prefix + "_" + level + "_tabular.xls")
            write_results(level_result, output_file, query_files, [level])

    LOGGER.info('6) Done'.format(output_directory))


if __name__ == "__main__":
    main()
