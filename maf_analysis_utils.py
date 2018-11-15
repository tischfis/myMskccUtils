#written by Noah Friedman
#funcions for performing analyses and functions on mafs 
import sys
import argparse
import os
import pandas as pd
import numpy as np

from collections import Counter
sys.path.append('/ifs/work/taylorlab/friedman/')

pathPrefix = ''
if os.getcwd() == '/Users/friedman/Desktop/mnt':
	pathPrefix = '/Users/friedman/Desktop/mnt'

import imp
analysis_utils = imp.load_source('analysis_utils', pathPrefix + '/ifs/work/taylorlab/friedman/myUtils/analysis_utils.py')

#OMNIBUS maf prepping function (adds tid, pid etc)
def prep_maf(df,
			sampleNameCol='Tumor_Sample_Barcode',
			pid=True, tid=True, quadNuc=True, cancerType=True,
			secondSig=None):

	if tid: df['tid'] = df[sampleNameCol].apply(lambda x: x[:13])
	if pid: df['pid'] = df[sampleNameCol].apply(lambda x: x[:9])
	if quadNuc:
		df['quadNuc'] = df.apply(lambda row: 
   			mutationSigUtils.create_reference_four_nuc(row['Ref_Tri'], row['Reference_Allele'], row['Tumor_Seq_Allele2'])
    		if row['Variant_Type'] == 'SNP' else None, axis=1)
	if cancerType:
		cDict = analysis_utils.get_cancer_type_information(cancerTypeDfPath = pathPrefix +'/ifs/work/taylorlab/friedman/msk-impact/msk-impact/data_clinical_sample.txt')
		df['cancer_type'] = df['pid'].apply(lambda x: cDict[x] if x in cDict else None)
	
	if secondSig != None: #mark the second most common signature
		pass
	return df

#a utility function designed to add information about hotspots (which hotspot, what 4nuc etc) to a df with one entry per case
def add_hotspot_maf_info_to_df(df, mafDf,
 allHotspots, hotspotsToFocusOn, #a set of all hospots and a set of hotspots to focus on (those not to call 'other')
 idCol = 'pid', removeDups=True):
	hotspotsWeCareAbout = mafDf[mafDf['Amino_Acid_Change'].isin(allHotspots)]
	if removeDups:
		hotspotsWeCareAbout = hotspotsWeCareAbout.drop_duplicates(subset=[idCol], keep=False)
	hotspotLabelDict = dict(zip(hotspotsWeCareAbout[idCol], hotspotsWeCareAbout['Amino_Acid_Change']))

	hotspotFourNucDict = dict(zip(hotspotsWeCareAbout[idCol], hotspotsWeCareAbout['quadNuc']))
	df['Amino_Acid_Change'] = df[idCol].apply(lambda x: hotspotLabelDict[x] if x in hotspotLabelDict else None)
	df['Amino_Acid_Change_Adj'] = df[idCol].apply(lambda x:
		hotspotLabelDict[x] if (x in hotspotLabelDict and hotspotLabelDict[x] in hotspotsToFocusOn) else 'otherHotspot' if x in hotspotLabelDict else None)
	df['quadNuc'] = df[idCol].apply(lambda x: hotspotFourNucDict[x] if x in hotspotFourNucDict else None)
	return df


def summarize_per_case_mutation_info_for_mafs(mafDf):
	oncoKbOncogenicAnnotations = set(['Likely Oncogenic', 'Oncogenic', 'Predicted Oncogenic'])
	listOfDicts = []
	cases = set(mafDf['Tumor_Sample_Barcode'])
	cntr = 0
	for case in cases:
		if cntr%20==0: #slow function so I print progress
			print cntr, len(cases)
		localDict = {}
		caseDf = mafDf[mafDf['Tumor_Sample_Barcode'] == case]
		nOncogenicMuts = caseDf[caseDf['oncogenic'].isin(oncoKbOncogenicAnnotations)].shape[0]
		nHotspotMuts = caseDf[caseDf['is-a-hotspot'] == 'Y'].shape[0]
		nActivatingMutations = caseDf[(caseDf['is-a-hotspot'] == 'Y') | (caseDf['oncogenic'].isin(oncoKbOncogenicAnnotations))].shape[0]
		nMut = caseDf.shape[0]

		localDict['Nmut'] = nMut
		localDict['nOncogenicMuts'] = nOncogenicMuts
		localDict['nHotspotMuts'] = nHotspotMuts
		localDict['nActivatingMutations'] = nActivatingMutations

		listOfDicts.append(localDict)
		cntr += 1

	return pd.DataFrame(listOfDicts)

#a function that enumerates all activating mutations in a gene across a cohort maf
def enumerate_activating_muts_across_cohort(gene, mafDf = None):

	#TODO appropriately allow the user to load the maf df if there is no default
	#if mafDf.sh:
	#	mafDf = pd.read_table('/ifs/work/taylorlab/friedman/myAdjustedDataFiles/annotatedOncoPlusHotspotMafAllImpact_trinuc')

	oncogenicMutColNames = set(['Likely Oncogenic', 'Oncogenic', 'Predicted Oncogenic'])
	geneOncogenicOrHotspotMuts = mafDf[(mafDf['Hugo_Symbol'] == gene) &((mafDf['is-a-hotspot'] == 'Y') |(mafDf['oncogenic'].isin(oncogenicMutColNames)))]

	#colsToKeep = ['Tumor_Sample_Barcode', 'is-a-hotspot', 'oncogenic', 'Ref_Tri', 'Tumor_Seq_Allele2', 'Reference_Allele']
	#return geneOncogenicOrHotspotMuts[[colsToKeep]]
	return geneOncogenicOrHotspotMuts

#a function that given a maf of mutaitons and quadnuc spectra enriched for a signature returns the number of mutations that occur at the enriched spectra
def summarize_signature_attribution_for_case(mafDf, enrichedSigMotifs):
	oncogenicMutColNames = set(['Likely Oncogenic', 'Oncogenic', 'Predicted Oncogenic'])

	listOfDicts = []
	cases = set(mafDf['Tumor_Sample_Barcode'])
	for case in cases:
		localD = {}
		caseDf = mafDf[mafDf['Tumor_Sample_Barcode'] == case]

		#get a maf for the current cases hotspot and oncogenic muts 
		hotspotMutDf = caseDf[caseDf['is-a-hotspot'] == 'Y']
		oncogenicMutDf = caseDf[caseDf['oncogenic'].isin(oncogenicMutColNames)]
		nHotspotMutations = hotspotMutDf.shape[0]
		nOncogenicMutations = oncogenicMutDf.shape[0]

		#get data about how many of each occurs at a motif
		nOncogenicMutationsAtEnrichedMotif = oncogenicMutDf[oncogenicMutDf['quadNuc'].isin(enrichedSigMotifs)].shape[0]
		nHotpsotMutationsAtEnrichedMotif = hotspotMutDf[hotspotMutDf['quadNuc'].isin(enrichedSigMotifs)].shape[0]
		nMut = caseDf.shape[0]

		#append info to the local dictionary (row of the future df)
		localD['Tumor_Sample_Barcode'] = case
		localD['nHotspots'] = nHotspotMutations
		localD['Nmut'] = nMut
		localD['nOncogenicMutations'] = nOncogenicMutations
		localD['nOncogenicMutationsAtEnrichedMotif'] = nOncogenicMutationsAtEnrichedMotif
		localD['nHotpsotMutationsAtEnrichedMotif'] = nHotpsotMutationsAtEnrichedMotif  

		listOfDicts.append(localD)

	df = pd.DataFrame(listOfDicts)
	return df      

#returns a dataframe with the cases that have mutations in a gene and the type of mutation in that gene
#note the way we return it is designed for the R long format
def asses_per_case_mut_info_for_gene(mafDf, gene, quadnucSet):

	def classify_mut_residue_data(quadNucs, qNucSet):
		mutType = None
		if len(quadNucs) == 1: #if there is only one quadnuc mutation figure out which type it is
			v = quadNucs.pop()
			if v in qNucSet: return 'favoredMutation'
			else: return 'notFavoredMutation'
		else: #if there are more than one mutations in the gene we need to classify whether the mutations are mixed, from the favored process only or from both
			nFavoredMutations = 0
			nNotFavoredMutations = 0
			for v in quadNucs:
				if v in qNucSet:
					nFavoredMutations += 1
				else:
					nNotFavoredMutations += 1
				if nFavoredMutations >= 1 and nNotFavoredMutations >= 1:
					return 'mixed'
				elif nFavoredMutations >= 1:
					return 'mutlipleFavoredMutation'
				else:
					return 'multipleNotFavoredMutation'

	cases = set(mafDf['Tumor_Sample_Barcode'])
	geneMuts = mafDf[mafDf['Hugo_Symbol'] == gene]
	#we only put information in the dataframe we return if there are snp muts
	listOfDicts = []
	for case in cases:
		caseMuts = geneMuts[geneMuts['Tumor_Sample_Barcode'] == case]
		caseQuadNucs = set(caseMuts['quadNuc'])
		if len(caseQuadNucs) != 0:
			if None not in caseQuadNucs:
				classification = classify_mut_residue_data(caseQuadNucs, quadnucSet)
				localD = dict()
				localD['gene'] = gene
				localD['Tumor_Sample_Barcode'] = case
				localD['mutClassification'] = classification
				localD['nGeneMut'] = len(caseQuadNucs)
				listOfDicts.append(localD)
	return pd.DataFrame(listOfDicts)

def main():

	parser = argparse.ArgumentParser(description='Arg parser for this script')
	parser.add_argument('--argument', help='stub for parser argument', default='')

	args = parser.parse_args()

if __name__ == '__main__':
    main()















