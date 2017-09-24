import os

def options(opt):
    opt.load(['compiler_c','compiler_cxx','gnu_dirs','ipac','irsa',
              'pqxx','cfitsio','boost','wcs','gsoap'])

def configure(conf):
    conf.load(['compiler_c','compiler_cxx','gnu_dirs','ipac','irsa',
               'pqxx','cfitsio','boost','wcs','gsoap'])
    conf.check_boost(lib='filesystem system regex')
    
def build(bld):
    default_flags=['-Wall', '-Wextra', '-O2']
    default_flags.append('-DIBE_DATA_ROOT="' + bld.env.IRSA_DIR + '/web/html/ibe/data"')

    bld.program(source=['src/Access.cpp',
                        'src/Cgi.cpp',
                        'src/Cutout.cpp',
                        'src/nph-serve.cpp'],
                target='nph-ibe_data',
                cxxflags=default_flags,
                use=['BOOST','ipac','irsa_sso','pqxx','cfitsio','wcs','gsoap'],
                install_path=bld.env.WEB_CGI_DIR + '/ibe'
    )

    bld.install_files(bld.env.HTML_DIR + '/ibe',bld.path.ant_glob("html/**"),
                      cwd=bld.path.find_dir('html'), relative_trick=True);

    data_dir = bld.env.HTML_DIR + '/ibe/data/'
    # 2MASS
    bld.symlink_as(data_dir + 'twomass/sixxcat/sixxcat',
                   '/stage/tmass-data/links/sixxcatalog')
    bld.symlink_as(data_dir + 'twomass/calibration/calibration',
                   '/stage/tmass-data/links/calibration')
    bld.symlink_as(data_dir + 'twomass/allsky/allsky',
                   '/stage/tmass-data/links/allsky')
    bld.symlink_as(data_dir + 'twomass/full/full',
                   '/stage/tmass-data/links/full')
    bld.symlink_as(data_dir + 'twomass/sixxfull/sixxfull',
                   '/stage/tmass-data/links/sixxfull')
    bld.symlink_as(data_dir + 'twomass/mosaic/sixdeg',
                   '/stage/irsa-data-2mass-mosaic/links/mosaic/sixdeg')
    bld.symlink_as(data_dir + 'twomass/lga/images',
                   '/irsadata/2MASS/LGA/images')
    bld.symlink_as(data_dir + 'twomass/lh/images',
                   '/irsadata/LH/images')
    
    # WISE
    bld.symlink_as(data_dir + 'wise/neowiser/p1bm_frm',
                   '/stage/irsa-wise-links-public/links-neowiser/l1b')
    bld.symlink_as(data_dir + 'wise/prelim_postcryo/p1bm_frm',
                   '/stage/irsa-wise-links-public/links-prelim-postcryo/l1b-2band')
    bld.symlink_as(data_dir + 'wise/cryo_3band/3band_p3am_cdd',
                   '/stage/irsa-wise-links-public/links-3band/l3a-3band')
    bld.symlink_as(data_dir + 'wise/cryo_3band/3band_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-3band/l1b-3band')
    bld.symlink_as(data_dir + 'wise/postcryo/2band_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-postcryo/l1b-2band')
    bld.symlink_as(data_dir + 'wise/prelim/p1bm_frm',
                   '/stage/irsa-wise-links-public/links-prelim/l1b')
    bld.symlink_as(data_dir + 'wise/prelim/p3am_cdd',
                   '/stage/irsa-wise-links-public/links-prelim/l3a')
    bld.symlink_as(data_dir + 'wise/allsky/4band_p3am_cdd',
                   '/stage/irsa-wise-links-public/links-allsky/l3a-4band')
    bld.symlink_as(data_dir + 'wise/allsky/4band_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-allsky/l1b-4band')
    bld.symlink_as(data_dir + 'wise/allwise/p3am_cdd',
                   '/stage/irsa-wise-links-public/links-allwise/l3a')
    bld.symlink_as(data_dir + 'wise/merge/merge_p1bm_frm',
                   '/stage/irsa-wise-links-public/links-merge/l1b')
    bld.symlink_as(data_dir + 'wise/merge/merge_p3am_cdd',
                   '/stage/irsa-wise-links-public/links-merge/l3a')

    # PTF
    bld.symlink_as(data_dir + 'ptf/images/level1',
                   '/stage/irsa-ptf-links/')
    bld.symlink_as(data_dir + 'ptf/images/level2',
                   '/stage/irsa-ptf-links/refims-links')

    # ZTF
    bld.symlink_as(data_dir + 'ztf/products/raw',
                   '/stage/irsa-ztf-links/ingest-test/raw')
    bld.symlink_as(data_dir + 'ztf/products/cal',
                   '/stage/irsa-ztf-links/ingest-test/cal')
    bld.symlink_as(data_dir + 'ztf/products/sci',
                   '/stage/irsa-ztf-links/ingest-test/sci')

    # Spitzer
    bld.symlink_as(data_dir + 'spitzer/sha/archive',
                   '/irsadata/SPITZER/SHA/archive')

    bld.symlink_as(data_dir + 'spitzer/seip_science/images',
                   '/irsadata/SPITZER/Enhanced/SEIP/images')
    bld.symlink_as(data_dir + 'spitzer/seip_ancillary/images',
                   '/irsadata/SPITZER/Enhanced/SEIP/images')
    bld.symlink_as(data_dir + 'spitzer/abell1763_images/images',
                   '/irsadata/SPITZER/Abell1763/images')
    
    bld.symlink_as(data_dir + 'spitzer/c2d_images_irac_all/images',
                   '/irsadata/SPITZER/C2D/images')
    bld.symlink_as(data_dir + 'spitzer/c2d_images_mips_all/images',
                   '/irsadata/SPITZER/C2D/images')
    bld.symlink_as(data_dir + 'spitzer/c2d_images_av/images',
                   '/irsadata/SPITZER/C2D/images')
    bld.symlink_as(data_dir + 'spitzer/c2d_images_bolocam/images',
                   '/irsadata/SPITZER/C2D/images')
    
    bld.symlink_as(data_dir + 'spitzer/clash_images/images',
                   '/irsadata/SPITZER/CLASH/images')
    
    bld.symlink_as(data_dir + 'spitzer/cygnus_x_images_mosaics/images',
                   '/irsadata/SPITZER/Cygnus-X/images')
    bld.symlink_as(data_dir + 'spitzer/cygnus_x_images_tiles/images',
                   '/irsadata/SPITZER/Cygnus-X/images')
    bld.symlink_as(data_dir + 'spitzer/cygnus_x_images_phot_mos/images',
                   '/irsadata/SPITZER/Cygnus-X/images')
    
    bld.symlink_as(data_dir + 'spitzer/dustings_images/galaxies',
                   '/irsadata/SPITZER/DUSTiNGS/galaxies')
    bld.symlink_as(data_dir + 'spitzer/feps_images/images',
                   '/irsadata/SPITZER/FEPS/images')
    
    bld.symlink_as(data_dir + 'spitzer/fls_gbt_hi/images',
                   '/irsadata/SPITZER/FLS/images')
    bld.symlink_as(data_dir + 'spitzer/fls_irac/images',
                   '/irsadata/SPITZER/FLS/images')
    bld.symlink_as(data_dir + 'spitzer/fls_kpno_r/images',
                   '/irsadata/SPITZER/FLS/images')
    bld.symlink_as(data_dir + 'spitzer/fls_mips/images',
                   '/irsadata/SPITZER/FLS/images')
    bld.symlink_as(data_dir + 'spitzer/fls_sdss/images',
                   '/irsadata/SPITZER/FLS/images')
    bld.symlink_as(data_dir + 'spitzer/fls_vla/images',
                   '/irsadata/SPITZER/FLS/images')
    
    bld.symlink_as(data_dir + 'spitzer/fidel_images_24um/images',
                   '/irsadata/SPITZER/FIDEL/images')
    bld.symlink_as(data_dir + 'spitzer/fidel_images_70um/images',
                   '/irsadata/SPITZER/FIDEL/images')
    bld.symlink_as(data_dir + 'spitzer/fidel_images_160um/images',
                   '/irsadata/SPITZER/FIDEL/images')
    
    bld.symlink_as(data_dir + 'spitzer/glimpsei_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpsei_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpseii_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpseii_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpseii_sub/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse3d_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse3d_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse360_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse360_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_velacar_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_velacar_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_deepglimpse_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_deepglimpse_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_smog_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_smog_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_cygx_0_6/images',
                   '/irsadata/SPITZER/GLIMPSE/images')
    bld.symlink_as(data_dir + 'spitzer/glimpse_cygx_1_2/images',
                   '/irsadata/SPITZER/GLIMPSE/images')

    bld.symlink_as(data_dir + 'spitzer/goals_herschel/images',
                   '/irsadata/SPITZER/GOALS/images')
    bld.symlink_as(data_dir + 'spitzer/goals_spitzer/images',
                   '/irsadata/SPITZER/GOALS/images')

    bld.symlink_as(data_dir + 'spitzer/sgoods_irac_spitzer_dr3/images',
                   '/irsadata/SPITZER/GOODS/images')
    bld.symlink_as(data_dir + 'spitzer/sgoods_mips_spitzer_dr3/images',
                   '/irsadata/SPITZER/GOODS/images')
    bld.symlink_as(data_dir + 'spitzer/sgoods_irac_spitzer_dr2/images',
                   '/irsadata/SPITZER/GOODS/images')
    bld.symlink_as(data_dir + 'spitzer/sgoods_irs_spitzer/images',
                   '/irsadata/SPITZER/GOODS/images')
    bld.symlink_as(data_dir + 'spitzer/sgoods_ancillary_v1_0/images',
                   '/irsadata/SPITZER/GOODS/images')

    bld.symlink_as(data_dir + 'spitzer/iudf_mosaic/images',
                   '/irsadata/SPITZER/IUDF/images')
    
    bld.symlink_as(data_dir + 'spitzer/lvl_mips/images',
                   '/irsadata/SPITZER/LVL/images')
    bld.symlink_as(data_dir + 'spitzer/lvl_irac/images',
                   '/irsadata/SPITZER/LVL/images')
    bld.symlink_as(data_dir + 'spitzer/lvl_halpha/images',
                   '/irsadata/SPITZER/LVL/images')
    bld.symlink_as(data_dir + 'spitzer/lvl_galex/images',
                   '/irsadata/SPITZER/LVL/images')
    
    bld.symlink_as(data_dir + 'spitzer/m31irac_image/images',
                   '/irsadata/SPITZER/M31IRAC/images')
    bld.symlink_as(data_dir + 'spitzer/mips_lg_images/images',
                   '/irsadata/SPITZER/MIPS_LG/images')
    bld.symlink_as(data_dir + 'spitzer/mipsgal_images/images',
                   '/irsadata/SPITZER/MIPSGAL/images')
    bld.symlink_as(data_dir + 'spitzer/s4g_images/galaxies',
                   '/irsadata/SPITZER/S4G/galaxies')
    bld.symlink_as(data_dir + 'spitzer/safires_science/images',
                   '/irsadata/SPITZER/SAFIRES/images')
    bld.symlink_as(data_dir + 'spitzer/safires_ancillary/images',
                   '/irsadata/SPITZER/SAFIRES/images')

    bld.symlink_as(data_dir + 'spitzer/sage_mips_mos/images',
                   '/irsadata/SPITZER/SAGE/images')
    bld.symlink_as(data_dir + 'spitzer/sage_mips_tiles/images',
                   '/irsadata/SPITZER/SAGE/images')
    bld.symlink_as(data_dir + 'spitzer/sage_irac_mos/images',
                   '/irsadata/SPITZER/SAGE/images')
    bld.symlink_as(data_dir + 'spitzer/sage_spec_cubes/spectra',
                   '/irsadata/SPITZER/SAGE/spectra')
    bld.symlink_as(data_dir + 'spitzer/sage_irac_tiles/images',
                   '/irsadata/SPITZER/SAGE/images')
    bld.symlink_as(data_dir + 'spitzer/sage_smc_irac/images',
                   '/irsadata/SPITZER/SAGE-SMC/images')
    bld.symlink_as(data_dir + 'spitzer/sage_smc_mips/images',
                   '/irsadata/SPITZER/SAGE-SMC/images')

    bld.symlink_as(data_dir + 'spitzer/s_candels_images/images',
                   '/irsadata/SPITZER/S-CANDELS/images')

    bld.symlink_as(data_dir + 'spitzer/sdwfs_combined/images',
                   '/irsadata/SPITZER/SDWFS/images')
    bld.symlink_as(data_dir + 'spitzer/sdwfs_epoch1/images',
                   '/irsadata/SPITZER/SDWFS/images')
    bld.symlink_as(data_dir + 'spitzer/sdwfs_epoch2/images',
                   '/irsadata/SPITZER/SDWFS/images')
    bld.symlink_as(data_dir + 'spitzer/sdwfs_epoch3/images',
                   '/irsadata/SPITZER/SDWFS/images')
    bld.symlink_as(data_dir + 'spitzer/sdwfs_epoch4/images',
                   '/irsadata/SPITZER/SDWFS/images')

    bld.symlink_as(data_dir + 'spitzer/sep_images/images',
                   '/irsadata/SPITZER/SEP/images')
    bld.symlink_as(data_dir + 'spitzer/servs_images/images',
                   '/irsadata/SPITZER/SERVS/images')
    bld.symlink_as(data_dir + 'spitzer/shela_images/images',
                   '/irsadata/SPITZER/SHELA/images')
    bld.symlink_as(data_dir + 'spitzer/sings_images/galaxies',
                   '/irsadata/SPITZER/SINGS/galaxies')

    bld.symlink_as(data_dir + 'spitzer/simple_images_images/images',
                   '/irsadata/SPITZER/SIMPLE/images')
    bld.symlink_as(data_dir + 'spitzer/simple_images_epoch1/images',
                   '/irsadata/SPITZER/SIMPLE/images')
    bld.symlink_as(data_dir + 'spitzer/simple_images_epoch2/images',
                   '/irsadata/SPITZER/SIMPLE/images')

    bld.symlink_as(data_dir + 'spitzer/spies_images/images',
                   '/irsadata/SPITZER/SpIES/images')
    bld.symlink_as(data_dir + 'spitzer/spuds_images/images',
                   '/irsadata/SPITZER/SpUDS/images')
    bld.symlink_as(data_dir + 'spitzer/swire_images/images',
                   '/irsadata/SPITZER/SWIRE/images')

    bld.symlink_as(data_dir + 'spitzer/taurus_irac_ch1/images',
                   '/irsadata/SPITZER/Taurus/images')
    bld.symlink_as(data_dir + 'spitzer/taurus_irac_ch2/images',
                   '/irsadata/SPITZER/Taurus/images')
    bld.symlink_as(data_dir + 'spitzer/taurus_irac_ch3/images',
                   '/irsadata/SPITZER/Taurus/images')
    bld.symlink_as(data_dir + 'spitzer/taurus_irac_ch4/images',
                   '/irsadata/SPITZER/Taurus/images')
    bld.symlink_as(data_dir + 'spitzer/taurus_mips_24/images',
                   '/irsadata/SPITZER/Taurus/images')
    bld.symlink_as(data_dir + 'spitzer/taurus_mips_70/images',
                   '/irsadata/SPITZER/Taurus/images')
    bld.symlink_as(data_dir + 'spitzer/taurus_mips_160/images',
                   '/irsadata/SPITZER/Taurus/images')

    bld.symlink_as(data_dir + 'spitzer/frontier_images/images',
                   '/irsadata/SPITZER/Frontier/images')
    bld.symlink_as(data_dir + 'spitzer/elflock_atlas/images',
                   '/irsadata/ELFLock/images')

    # MUSYC
    bld.symlink_as(data_dir + 'musyc/musyc_images/images',
                   '/irsadata/MUSYC/images')

    # BLAST
    bld.symlink_as(data_dir + 'blast/blast_images/images',
                   '/irsadata/BLAST/images')

    # IRTS
    bld.symlink_as(data_dir + 'irts/irts_images/MAPS',
                   '/irsadata/IRTS/MAPS')

    # BOLOCAM GPS
    bld.symlink_as(data_dir + 'bolocam/bolocam_images_v1/images',
                   '/irsadata/BOLOCAM_GPS/images')
    bld.symlink_as(data_dir + 'bolocam/bolocam_images_v3/images',
                   '/irsadata/BOLOCAM_GPS/images')
    bld.symlink_as(data_dir + 'bolocam/bolocam_sharc2/images',
                   '/irsadata/BOLOCAM_GPS/images')

    # MSX
    bld.symlink_as(data_dir + 'msx/msx_images/images',
                   '/irsadata/MSX/images')
    
    # IRAS
    bld.symlink_as(data_dir + 'iras/issa_images/ISSA_complete_v2',
                   '/irsadata/IRAS/ISSA/ISSA_complete_v2')
    bld.symlink_as(data_dir + 'iras/iga_images/images',
                   '/irsadata/IRAS/IGA/images')
    bld.symlink_as(data_dir + 'iras/eiga_images/images',
                   '/irsadata/IRAS/EIGA/images')
    bld.symlink_as(data_dir + 'iras/iris_images/images',
                   '/irsadata/IRAS/IRIS/images')
    bld.symlink_as(data_dir + 'iras/miga_images/images',
                   '/irsadata/IRAS/MIGA/images')
    
    # COSMOS
    bld.symlink_as(data_dir + 'cosmos/cosmos_acs_2_0/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_cfht/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_chandra_merged/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_galex/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_irac/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_mips/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_kpno/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_nicmos/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_sdss/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_subaru/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_ukirt/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_vla/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_wfpc/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_xmm/images',
                   '/irsadata/COSMOS$/images')
    bld.symlink_as(data_dir + 'cosmos/cosmos_ultravista/images',
                   '/irsadata/COSMOS$/images')

    # Herschel
    bld.symlink_as(data_dir + 'herschel/acmc_images/images',
                   '/irsadata/Herschel/ACMC/images')
    bld.symlink_as(data_dir + 'herschel/coldcores_images/images',
                   '/irsadata/Herschel/ColdCores/images')
    bld.symlink_as(data_dir + 'herschel/dunes_mosaic/images',
                   '/irsadata/Herschel/dunes_mosaic/images')
    bld.symlink_as(data_dir + 'herschel/dunes_scan/images',
                   '/irsadata/Herschel/DUNES/images')
    bld.symlink_as(data_dir + 'herschel/dunes_chopnod/images',
                   '/irsadata/Herschel/DUNES/images')
    bld.symlink_as(data_dir + 'herschel/dunes_singleext/images',
                   '/irsadata/Herschel/DUNES/images')
    bld.symlink_as(data_dir + 'herschel/hgoods_images/images',
                   '/irsadata/Herschel/GOODS/images')
    bld.symlink_as(data_dir + 'herschel/helga_images/images',
                   '/irsadata/Herschel/HELGA/images')
    bld.symlink_as(data_dir + 'herschel/kingfish_images/galaxies',
                   '/irsadata/Herschel/KINGFISH/galaxies')
    bld.symlink_as(data_dir + 'herschel/heritage_images/images',
                   '/irsadata/Herschel/HERITAGE/images')
    bld.symlink_as(data_dir + 'herschel/hermes_images/images',
                   '/irsadata/Herschel/HerMES/images')
    bld.symlink_as(data_dir + 'herschel/herm33es_images/images',
                   '/irsadata/Herschel/HerM33es/images')
    bld.symlink_as(data_dir + 'herschel/hops_pacs/images',
                   '/irsadata/Herschel/HOPS/images')
    bld.symlink_as(data_dir + 'herschel/hops_spitzer/images',
                   '/irsadata/Herschel/HOPS/images')
    bld.symlink_as(data_dir + 'herschel/hpdp_images/spectra',
                   '/irsadata/Herschel/HPDP/spectra')
    bld.symlink_as(data_dir + 'herschel/mess_images/images',
                   '/irsadata/Herschel/MESS/images')
    bld.symlink_as(data_dir + 'herschel/pep_images/images',
                   '/irsadata/Herschel/PEP/images')
    # bld.symlink_as(data_dir + 'herschel/observations/images',
    #                '/irsadata/Herschel//images')
    bld.symlink_as(data_dir + 'herschel/vngs_images/images',
                   '/irsadata/Herschel/VNGS/images')
    bld.symlink_as(data_dir + 'herschel/vngs_spectra/spectra',
                   '/irsadata/Herschel/VNGS/spectra')
    bld.symlink_as(data_dir + 'herschel/hhli_pacs_photo/images',
                   '/irsadata/Herschel/HHLI/images')
    bld.symlink_as(data_dir + 'herschel/hhli_pacs_par/images',
                   '/irsadata/Herschel/HHLI/images')
    bld.symlink_as(data_dir + 'herschel/hhli_spire_photo/images',
                   '/irsadata/Herschel/HHLI/images')
    bld.symlink_as(data_dir + 'herschel/hhli_spire_par/images',
                   '/irsadata/Herschel/HHLI/images')

    # FIXME: No scrapbook.  That is served by a cgi program hst_preview.
    # FIXME: No NED.  It is served by going to NED.
