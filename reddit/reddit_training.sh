#!/usr/bin/env bash

declare -a arr=(12go74 5c8civ 13x6gq 2ldgl2 1ly1ry 1c0205 10xfh4 1h29ys 1in0wy 12rxes vqvgr 10ut81 18blji 12sous 10ycr2 znwy3 1ls5b1 10wy0o 5cl3as xtwwy 4af7tq 1m389a 11n2ue 1rlkd8 1cc5wr rjmjb 14v0nk 121ysa 1dzj1x 2lldg4 12f59n 12p6tm 5dm952 11xvl3 1ick3k 4lpxll 3p2mja 3lflcs 1uzynk 1ble64 z8b9t 1ito8k za73x 5c2f8o 4rnnq1 10xyfb 1irlr2 42tr1o 4h6obe 1rxcrj 11x0da 11btgd sk7sp 1eb5em 15c5j4 4uivhj 11dk5a 11oyn2 3oqnyc uomx8 1h9npe 25u3i7 11evbk 1d1asi 1z9qpv 1aj22m 1px2d3 12qc0h zfg0z 4qrmcv 1ctt0a 1d09zc 19crpe 45g21n 123ai1 3tazwn 3ic9ev 12vb7x 5byj5v 4v9ia2 1ivxxl 5cyzi2 z0n54 4ftp2k 1cjbct 10fc31 4ya1oq 1az3d1 181bk3 2l9y00 4085p0 11te1o 1105qu 1jfuay 10wr8m 3j19ug 1hpwwo 11q5z9 ywjkp 19l617)

for i in "${arr[@]}"
do
    ./fetch_reddit.py $i > raw/republican/$i.html
    ./parse_reddit.py $i > train/republican/$i.txt
done
